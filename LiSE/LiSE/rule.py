# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013-2014 Zachary Spector,  zacharyspector@gmail.com
""" The fundamental unit of game logic, the Rule, and structures to
store and organize them in.

A Rule is three lists of functions: triggers, prereqs, and actions.
The actions do something, anything that you need your game to do, but
probably making a specific change to the world model. The triggers and
prereqs between them specify when the action should occur: any of its
triggers can tell it to happen, but then any of its prereqs may stop it
from happening.

Rules are assembled into RuleBooks, essentially just lists of Rules
that can then be assigned to be followed by any game entity --
but each game entity has its own RuleBook by default, and you never really
need to change that.

"""
from collections import (
    Mapping,
    MutableMapping,
    MutableSequence,
    defaultdict
)
from functools import partial

from .util import (
    dispatch,
    listener,
    unlistener,
    listen,
    reify
)


class RuleFuncList(MutableSequence):
    def __init__(self, rule):
        self.rule = rule
        self._listeners = []

    def listener(self, f):
        return listener(self._listeners, f)

    def unlisten(self, f):
        return unlistener(self._listeners, f)

    @reify
    def _cache(self):
        self._cache_reified = True
        return list(self._loader(self.rule.name))

    def _nominate(self, v):
        if callable(v):
            if v.__name__ in self.funcstore:
                if self.funcstore[v.__name__] != v:
                    raise KeyError(
                        "Already have a {typ} function named {n}. "
                        "If you really mean to replace it, set "
                        "engine.{typ}[{n}]".format(
                            typ=self.typ,
                            n=v.__name__
                        )
                    )
            else:
                self.funcstore[v.__name__] = v
            v = v.__name__
        if v not in self.funcstore:
            raise KeyError("No {typ} function named {n}".format(
                typ=self.typ, n=v
            ))
        return v

    def __iter__(self):
        if self.rule.engine.caching:
            inner = self._cache
        else:
            inner = self._loader(self.rule.name)
        for funcname in inner:
            yield self.funcstore[funcname]

    def __len__(self):
        if self.rule.engine.caching:
            return len(self._cache)
        else:
            return len(list(self._loader(self.rule.name)))

    def __getitem__(self, i):
        if self.rule.engine.caching:
            return self._cache[i]
        else:
            return self._loader(self.rule.name)[i]

    def __setitem__(self, i, v):
        while i < 0:
            i += len(self)
        v = self._nominate(v)
        self._replacer(self.rule.name, i, v)
        if self.rule.engine.caching and hasattr(self, '_cache_reified'):
            self._cache[i] = v

    def __delitem__(self, i):
        while i < 0:
            i += len(self)
        self._deleter(self.rule.name, i)
        if self.rule.engine.caching and hasattr(self, '_cache_reified'):
            del self._cache[i]

    def insert(self, i, v):
        while i < 0:
            i += len(self)
        v = self._nominate(v)
        self._inserter(self.rule.name, i, v)
        if self.rule.engine.caching and hasattr(self, '_cache_reified'):
            self._cache.insert(i, v)

    def append(self, v):
        v = self._nominate(v)
        self._appender(self.rule.name, v)
        if self.rule.engine.caching and hasattr(self, '_cache_reified'):
            self._cache.append(v)


class TriggerList(RuleFuncList):
    @reify
    def funcstore(self):
        return self.rule.engine.trigger

    @reify
    def _loader(self):
        return self.funcstore.db.rule_triggers

    @reify
    def _replacer(self):
        return self.funcstore.db.replace_rule_trigger

    @reify
    def _inserter(self):
        return self.funcstore.db.insert_rule_trigger

    @reify
    def _deleter(self):
        return self.funcstore.db.delete_rule_trigger

    @reify
    def _appender(self):
        return self.funcstore.db.append_rule_trigger


class PrereqList(RuleFuncList):
    @reify
    def funcstore(self):
        return self.rule.engine.prereq

    @reify
    def _loader(self):
        return self.funcstore.db.rule_prereqs

    @reify
    def _replacer(self):
        return self.funcstore.db.replace_rule_prereq

    @reify
    def _inserter(self):
        return self.funcstore.db.insert_rule_prereq

    @reify
    def _deleter(self):
        return self.funcstore.db.delete_rule_prereq

    @reify
    def _appender(self):
        return self.funcstore.db.append_rule_prereq


class ActionList(RuleFuncList):
    @reify
    def funcstore(self):
        return self.rule.engine.action

    @reify
    def _loader(self):
        return self.funcstore.db.rule_actions

    @reify
    def _replacer(self):
        return self.funcstore.db.replace_rule_action

    @reify
    def _inserter(self):
        return self.funcstore.db.insert_rule_action

    @reify
    def _deleter(self):
        return self.funcstore.db.delete_rule_action

    @reify
    def _appender(self):
        return self.funcstore.db.append_rule_action


class Rule(object):
    """A collection of actions, being functions that enact some change on
    the world, which will be called each tick if and only if all of
    the prereqs return True, they being boolean functions that do not
    change the world.

    """
    @reify
    def _triggers(self):
        return TriggerList(self)

    @reify
    def _prereqs(self):
        return PrereqList(self)

    @reify
    def _actions(self):
        return ActionList(self)

    def __init__(
            self,
            engine,
            name,
            triggers=None,
            prereqs=None,
            actions=None
    ):
        """Store the engine and my name, make myself a record in the database
        if needed, and instantiate one FunList each for my triggers,
        actions, and prereqs.

        """
        self.engine = engine
        self.name = self.__name__ = name
        if name not in self.engine.rule:
            self.engine.rule.db.set_rule(name)
        if triggers:
            self.triggers.extend(triggers)
        if prereqs:
            self.prereqs.extend(prereqs)
        if actions:
            self.actions.extend(actions)
        self._trigger_results_cache = defaultdict(  # trigger
            lambda: defaultdict(  # branch
                lambda: defaultdict(  # tick
                    dict  # args: result
                )
            )
        )
        self._prereq_results_cache = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    dict
                )
            )
        )

    def __eq__(self, other):
        return (
            hasattr(other, 'name') and
            self.name == other.name
        )

    def __getattr__(self, attrn):
        if attrn == 'triggers':
            return self._triggers
        elif attrn == 'prereqs':
            return self._prereqs
        elif attrn == 'actions':
            return self._actions
        else:
            raise AttributeError("No attribute: {}".format(attrn))

    def _fun_names_iter(self, functyp, val):
        """Iterate over the names of the functions in ``val``,
        adding them to ``funcstore`` if they are missing;
        or if the items in ``val`` are already the names of functions
        in ``funcstore``, iterate over those.

        """
        funcstore = getattr(self.engine, functyp)
        for v in val:
            if callable(v):
                if v.__name__ in funcstore:
                    if funcstore[v.__name__] != v:
                        raise KeyError(
                            "Already have a {typ} function named "
                            "{k}. If you really mean to replace it, assign "
                            "it to engine.{typ}[{k}].".format(
                                typ=functyp,
                                k=v.__name__
                            )
                        )
                    else:
                        funcstore[v.__name__] = v
                else:
                    funcstore[v.__name__] = v
                yield v.__name__
            elif v not in funcstore:
                raise KeyError("Function {} not present in {}".format(
                    v, funcstore._tab
                ))
            else:
                yield v

    def __setattr__(self, attrn, val):
        if attrn == 'triggers':
            self.engine.trigger.db.replace_all_rule_triggers(
                self.name, list(self._fun_names_iter('trigger', val))
            )
        elif attrn == 'prereqs':
            self.engine.prereq.db.replace_all_rule_prereqs(
                self.name, list(self._fun_names_iter('prereq', val))
            )
        elif attrn == 'actions':
            self.engine.action.db.replace_all_rule_actions(
                self.name, list(self._fun_names_iter('action', val))
            )
        else:
            super().__setattr__(attrn, val)

    def __call__(self, engine, *args):
        """If at least one trigger fires, check the prereqs. If all the
        prereqs pass, perform the actions.

        After each call to a trigger, prereq, or action, the sim-time
        is reset to what it was before the rule was called.

        """
        if not self.check_triggers(engine, *args):
            return []
        if not self.check_prereqs(engine, *args):
            return []
            # maybe a result object that informs you as to why I
            # didn't run?
        return self.run_actions(engine, *args)

    def __repr__(self):
        return 'Rule({})'.format(self.name)

    def trigger(self, fun):
        """Decorator to append the function to my triggers list."""
        self._triggers.append(fun)
        return fun

    def prereq(self, fun):
        """Decorator to append the function to my prereqs list."""
        self._prereqs.append(fun)
        return fun

    def action(self, fun):
        """Decorator to append the function to my actions list."""
        self._actions.append(fun)
        return fun

    def duplicate(self, newname):
        """Return a new rule that's just like this one, but under a new
        name.

        """
        if self.engine.rule.db.haverule(newname):
            raise KeyError("Already have a rule called {}".format(newname))
        return Rule(
            self.engine,
            newname,
            list(self.triggers),
            list(self.prereqs),
            list(self.actions)
        )

    def always(self):
        """Arrange to be triggered every tick, regardless of circumstance."""
        def truth(*args):
            return True
        self.triggers = [truth]

    def check_triggers(self, engine, *args):
        """Run each trigger in turn. If one returns True, return True
        myself. If none do, return False.

        """
        curtime = (branch, tick) = engine.time
        for trigger in self.triggers:
            if not (
                trigger.__name__ in self._trigger_results_cache and
                branch in self._trigger_results_cache[trigger.__name__] and
                tick in self._trigger_results_cache[trigger.__name__][branch] and
                args in self._trigger_results_cache[trigger.__name__][branch][tick]
            ):
                self._trigger_results_cache[trigger.__name__][branch][tick][args] = trigger(engine, *args)
            result = self._trigger_results_cache[trigger.__name__][branch][tick][args]
            if engine.time != curtime:
                engine.time = curtime
            if result:
                return True
        return False

    def check_prereqs(self, engine, *args):
        """Run each prereq in turn. If all return True, return True myself. If
        one doesn't, return False.

        """
        curtime = (branch, tick) = engine.time
        for prereq in self.prereqs:
            if not(
                prereq.__name__ in self._prereq_results_cache and
                branch in self._prereq_results_cache[prereq.__name__] and
                tick in self._prereq_results_cache[prereq.__name__][branch] and
                args in self._prereq_results_cache[prereq.__name__][branch][tick]
            ):
                self._prereq_results_cache[prereq.__name__][branch][tick][args] = prereq(self.engine, *args)
            result = self._prereq_results_cache[prereq.__name__][branch][tick][args]
            engine.time = curtime
            if not result:
                return False
        return True

    def run_actions(self, engine, *args):
        """Run all my actions and return a list of their results.

        """
        curtime = engine.time
        r = []
        for action in self.actions:
            r.append(action(engine, *args))
            engine.time = curtime
        return r


class RuleBook(MutableSequence):
    """A list of rules to be followed for some Character, or a part of it
    anyway.

    """
    @reify
    def _cache(self):
        if self.name not in self.engine._rulebooks_cache:
            self.engine._rulebooks_cache[self.name] = list(
                self.engine.rule.db.rulebook_rules(self.name)
            )
        return self.engine._rulebooks_cache[self.name]

    def __init__(self, engine, name):
        self.engine = engine
        self.name = name
        self._listeners = []

    def __contains__(self, v):
        if self.engine.caching:
            cache = self._cache
        else:
            cache = list(self.engine.rule.db.rulebook_rules(self.name))
        if isinstance(v, Rule):
            v = v.name
        return v in cache

    def __iter__(self):
        if self.engine.caching:
            for rulen in self._cache:
                yield self.engine.rule[rulen]
            return
        for rule in self.engine.db.rulebook_rules(self.name):
            yield self.engine.rule[rule]

    def __len__(self):
        if self.engine.caching:
            return len(self._cache)
        return self.engine.rule.db.ct_rulebook_rules(self.name)

    def __getitem__(self, i):
        if self.engine.caching:
            return self.engine.rule[self._cache[i]]
        return self.engine.rule[
            self.engine.rule.db.rulebook_get(
                self.name,
                i
            )
        ]

    def _dispatch(self):
        self.engine.rulebook.dispatch(self)

    def _activate_rule(self, rule, active=True):
        (branch, tick) = self.engine.time
        self.engine.db.set_rule_activeness(  # world DB, not code DB
            self.name,
            rule.name,
            branch,
            tick,
            active
        )

    def __setitem__(self, i, v):
        if isinstance(v, Rule):
            rule = v
        elif isinstance(v, str):
            rule = self.engine.rule[v]
        else:
            rule = Rule(self.engine, v)
        self.engine.rule.db.rulebook_set(self.name, i, rule.name)
        self._activate_rule(rule)
        if self.engine.caching:
            while len(self._cache) <= i:
                self._cache.append(None)
            self._cache[i] = rule.name
        self._dispatch()

    def insert(self, i, v):
        self.engine.rule.db.rulebook_decr(self.name, i)
        self[i] = v

    def index(self, v):
        if isinstance(v, str):
            i = 0
            for rule in self:
                if rule.name == v:
                    return i
                i += 1
            else:
                raise ValueError(
                    "No rule named {} in rulebook {}".format(
                        v, self.name
                    )
                )
        return super().index(v)

    def __delitem__(self, i):
        self.engine.db.rulebook_del(self.name, i)
        if self.engine.caching:
            del self._cache[i]
        self._dispatch()

    def listener(self, fun):
        self.engine.rulebook.listener(rulebook=self.name)(fun)


class RuleMapping(MutableMapping):
    """Wraps a :class:`RuleBook` so you can get its rules by name.

    You can access the rules in this either dictionary-style or as
    attributes. This is for convenience if you want to get at a rule's
    decorators, eg. to add an Action to the rule.

    Using this as a decorator will create a new rule, named for the
    decorated function, and using the decorated function as the
    initial Action.

    Using this like a dictionary will let you create new rules,
    appending them onto the underlying :class:`RuleBook`; replace one
    rule with another, where the new one will have the same index in
    the :class:`RuleBook` as the old one; and activate or deactivate
    rules. The name of a rule may be used in place of the actual rule,
    so long as the rule already exists.

    You can also set a rule active or inactive by setting it to
    ``True`` or ``False``, respectively. Inactive rules are still in
    the rulebook, but won't be followed.

    """
    def __init__(self, engine, rulebook):
        self.engine = engine
        if isinstance(rulebook, RuleBook):
            self.rulebook = rulebook
        else:
            self.rulebook = RuleBook(engine, rulebook)
        self._listeners = defaultdict(list)
        self._rule_cache = {}

    def listener(self, f=None, rule=None):
        return listener(self._listeners, f, rule)

    def _dispatch(self, rule, active):
        dispatch(self._listeners, rule.name, self, rule, active)

    def _activate_rule(self, rule, active=True):
        if rule not in self.rulebook:
            self.rulebook.append(rule)
        else:
            self.rulebook._activate_rule(rule, active)
        self._dispatch(rule, active)

    def __repr__(self):
        return 'RuleMapping({})'.format([k for k in self])

    def __iter__(self):
        return self.engine.db.active_rules_rulebook(
            self.rulebook.name,
            *self.engine.time
        )

    def __len__(self):
        n = 0
        for rule in self:
            n += 1
        return n

    def __contains__(self, k):
        return self.engine.db.active_rule_rulebook(
            self.rulebook.name,
            k,
            *self.engine.time
        )

    def __getitem__(self, k):
        if k not in self:
            raise KeyError("Rule '{}' is not in effect".format(k))
        if k not in self._rule_cache:
            self._rule_cache[k] = Rule(self.engine, k)
            self._rule_cache[k].active = True
        return self._rule_cache[k]

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError

    def __setitem__(self, k, v):
        if isinstance(v, bool):
            if k not in self:
                raise KeyError(
                    "Can't activate or deactivate {}, "
                    "because it is not in my rulebook ({}).".format(
                        k, self.rulebook.name
                    )
                )
            self._activate_rule(k, v)
            return
        elif v in self.engine.rule:
            v = self.engine.rule[v]
        elif v in self.engine.function:
            v = self.engine.function[v]
        if isinstance(v, Rule):
            # may raise ValueError
            try:
                i = self.rulebook.index(k)
                if self.rulebook[i] != v:
                    self.rulebook[i] = v
            except ValueError:
                self._activate_rule(v)
        elif callable(v):
            if k in self.engine.rule:
                raise KeyError(
                    "Already have a rule named {name}. "
                    "If you really mean to replace it, set "
                    "self.rule[{name}] to a new Rule object.".format(name=k)
                )
            # create a new rule, named k, performing action v
            self.engine.rule[k] = v
            rule = self.engine.rule[k]
            self._activate_rule(rule)

    def __call__(self, v=None, name=None, always=False):
        def wrap(name, always, v):
            name = name if name is not None else v.__name__
            self[name] = v
            r = self[name]
            if always:
                r.always()
            return r
        if v is None:
            return partial(wrap, name, always)
        return wrap(name, always, v)

    def __delitem__(self, k):
        i = self.rulebook.index(k)
        del self.rulebook[i]
        self._dispatch(k, None)


class RuleFollower(object):
    """Interface for that which has a rulebook associated, which you can
    get a :class:`RuleMapping` into

    """
    @reify
    def _rule_mapping(self):
        return self._get_rule_mapping()

    @property
    def rule(self, v=None, name=None):
        if v is not None:
            return self._rule_mapping(v, name)
        return self._rule_mapping

    @reify
    def _rulebook_listeners(self):
        return []

    @property
    def rulebook(self):
        if not hasattr(self, '_rulebook'):
            self._upd_rulebook()
        return self._rulebook

    @rulebook.setter
    def rulebook(self, v):
        n = v.name if isinstance(v, RuleBook) else v
        self._set_rulebook_name(n)
        self._dispatch_rulebook(v)
        self._upd_rulebook()

    def _upd_rulebook(self):
        self._rulebook = self._get_rulebook()
        for f in self._rulebook_listeners:
            f(self, self._rulebook)

    def _get_rulebook(self):
        return RuleBook(
            self.engine,
            self._get_rulebook_name()
        )

    def rules(self):
        if not hasattr(self, 'engine'):
            raise AttributeError("Need an engine before I can get rules")
        for (rulen, active) in self._rule_names():
            if (
                hasattr(self.rule, '_rule_cache') and
                rulen in self.rulebook._rule_cache
            ):
                rule = self.rule._rule_cache[rulen]
            else:
                rule = Rule(self.engine, rulen)
            rule.active = active
            yield rule

    def rulebook_listener(self, f):
        listen(self._rulebook_listeners, f)

    def _rule_names_activeness(self):
        """Iterate over pairs of rule names and their activeness for each rule
        in my rulebook.

        """
        raise NotImplementedError

    def _get_rule_mapping(self):
        """Get the :class:`RuleMapping` for my rulebook."""
        raise NotImplementedError

    def _get_rulebook_name(self):
        """Get the name of my rulebook."""
        raise NotImplementedError

    def _set_rulebook_name(self, n):
        """Tell the database that this is the name of the rulebook to use for
        me.

        """
        raise NotImplementedError


class AllRuleBooks(Mapping):
    def __init__(self, engine, db):
        self.engine = engine
        self.db = db
        self.db.init_table('rulebooks')
        self._cache = {}
        self._listeners = defaultdict(list)

    def __iter__(self):
        yield from self.db.rulebooks()

    def __len__(self):
        return self.db.ct_rulebooks()

    def __contains__(self, k):
        if k in self._cache:
            return self._cache[k]
        return self.db.ct_rulebook_rules(k) > 0

    def __getitem__(self, k):
        if k not in self._cache:
            self._cache[k] = RuleBook(self.engine, k)
        return self._cache[k]

    def listener(self, f=None, rulebook=None):
        return listener(self._listeners, f, rulebook)

    def dispatch(self, rulebook):
        for fun in self._listeners[rulebook.name]:
            fun(rulebook)


# TODO: fix null rulebooks
#
# It appears that when you create a rule here it gets assigned
# to a null rulebook in the database. That's not very useful and might
# cause bad effects later on.
class AllRules(MutableMapping):
    def __init__(self, engine, db):
        self.engine = engine
        self.db = db
        self.db.init_table('rules')
        self.db.init_table('rulebooks')
        self._cache = {}
        self._listeners = defaultdict(list)

    def listener(self, f=None, rule=None):
        return listener(self._listeners, f, rule)

    def dispatch(self, rule, active):
        dispatch(self._listeners, rule.name, active, self, rule, active)

    def __iter__(self):
        yield from self.db.allrules()

    def __len__(self):
        return self.db.ctrules()

    def __contains__(self, k):
        try:
            return self.db.haverule(k)
        except TypeError:
            return False

    def __getitem__(self, k):
        if k not in self:
            raise KeyError("No such rule: {}".format(k))
        if k not in self._cache:
            self._cache[k] = Rule(self.engine, k)
        return self._cache[k]

    def __setitem__(self, k, v):
        if v in self.engine.action:
            v = self.engine.action[v]
        elif v in self.engine.function:
            v = self.engine.function[v]
        elif v in self.engine.rule:
            v = self.engine.rule[v]
        if callable(v):
            if k not in self._cache:
                self._cache[k] = Rule(self.engine, k)
            new = self._cache[k]
            new.actions = [v]
        elif isinstance(v, Rule):
            self._cache[k] = v
            new = v
        else:
            raise TypeError(
                "Don't know how to store {} as a rule.".format(type(v))
            )
        self.dispatch(new, True)

    def __delitem__(self, k):
        if k not in self:
            raise KeyError("No such rule")
        old = self[k]
        self.db.ruledel(k)
        self.dispatch(old, False)

    def __call__(self, v=None, name=None):
        if v is None and name is not None:
            def r(f):
                self[name] = f
                return self[name]
            return r
        k = name if name is not None else v.__name__
        self[k] = v
        return self[k]

    def new_empty(self, name):
        if name in self:
            raise KeyError("Already have rule {}".format(name))
        new = Rule(self.engine, name)
        self._cache[name] = new
        self.dispatch(new, True)
        return new