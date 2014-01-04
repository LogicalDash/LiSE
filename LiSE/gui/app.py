from os import sep

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import (
    BoundedNumericProperty,
    ObjectProperty,
    ListProperty,
    StringProperty)

from kivy.graphics import Line, Color

from kivy.uix.widget import Widget
from kivy.uix.stacklayout import StackLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.factory import Factory

from sqlite3 import connect, OperationalError

from LiSE.gui.board import (
    Pawn,
    Spot,
    Arrow,
    BoardView)
from LiSE.gui.board.arrow import get_points
from LiSE.gui.kivybits import TouchlessWidget, ImgStack
from LiSE.gui.swatchbox import SwatchBox, TogSwatch
from LiSE.gui.charsheet import CharSheetAdder
from LiSE.util import TimestreamException, tabclas
from LiSE.closet import Thing, mkdb, load_closet
from LiSE import __path__

Factory.register('BoardView', cls=BoardView)
Factory.register('SwatchBox', cls=SwatchBox)
Factory.register('TogSwatch', cls=TogSwatch)


class DummyPawn(ImgStack):
    """Looks like a Pawn, but doesn't have a Thing associated.

This is meant to be used when the user is presently engaged with
deciding where a Thing should be, when the Thing in question doesn't
exist yet, but you know what it should look like."""
    name = StringProperty()
    board = ObjectProperty()
    callback = ObjectProperty()

    def on_touch_up(self, touch):
        """Create a real Pawn on top of the Spot I am on top of, along
        with a Thing for it to represent. Then disappear."""
        for spot in self.board.spotlayout.children:
            if self.collide_widget(spot):
                obsrvr = unicode(self.board.facade.observer)
                obsrvd = unicode(self.board.facade.observed)
                hostn = unicode(self.board.host)
                placen = unicode(spot.place)
                tinybone = Thing.bonetype(
                    character=obsrvd,
                    name=self.name,
                    host=hostn)
                bigbone = Thing.bonetypes["thing_loc"](
                    character=obsrvd,
                    name=self.name,
                    branch=self.closet.branch,
                    tick=self.closet.tick,
                    location=placen)
                self.closet.set_bone(tinybone)
                self.closet.set_bone(bigbone)
                th = self.board.facade.observed.make_thing(self.name)
                thingn = unicode(th)
                branch = self.closet.branch
                tick = self.closet.tick
                for layer in xrange(0, len(self.bones)):
                    pawnbone = Pawn.bonetype(
                        observer=obsrvr,
                        observed=obsrvd,
                        host=hostn,
                        thing=thingn,
                        layer=layer,
                        branch=branch,
                        tick=tick,
                        img=self.bones[layer].name)
                    self.closet.set_bone(pawnbone)
                pawn = Pawn(board=self.board, thing=th)
                self.board.pawndict[thingn] = pawn
                self.board.pawnlayout.add_widget(pawn)
                self.clear_widgets()
                self.callback()
                return True


class SpriteMenuContent(StackLayout):
    closet = ObjectProperty()
    skel = ObjectProperty()
    selection = ListProperty([])
    picker_args = ListProperty([])

    def get_text(self, stringn):
        return self.closet.get_text(stringn)

    def upd_selection(self, togswatch, state):
        if state == 'normal':
            while togswatch in self.selection:
                self.selection.remove(togswatch)
        else:
            if togswatch not in self.selection:
                self.selection.append(togswatch)

    def validate_name(self, name):
        """Return True if the name hasn't been used for a Place in this Host
        before, False otherwise."""
        # assume that this is an accurate record of places that exist
        return name not in self.skel

    def aggregate(self):
        """Collect the place name and graphics set the user has chosen."""
        if len(self.selection) < 1:
            return False
        else:
            assert(len(self.selection) == 1)
        namer = self.ids.namer
        tog = self.selection.pop()
        if self.validate_name(namer.text):
            self.picker_args.append(namer.text)
            if len(tog.tags) > 0:
                self.picker_args.append(tog.tags)
            else:
                self.picker_args.append(tog.img)
            return True
        else:
            self.selection.append(tog)
            namer.text = ''
            namer.hint_text = "That name is taken. Try another."
            namer.background_color = [1, 0, 0, 1]
            namer.focus = False

            def unbg(*args):
                namer.background_color = [1, 1, 1, 1]
            Clock.schedule_once(unbg, 0.5)
            return False


class SpotMenuContent(SpriteMenuContent):
    pass


class PawnMenuContent(SpriteMenuContent):
    pass


class LiSELayout(FloatLayout):
    """A very tiny master layout that contains one board and some menus
and charsheets.

    """
    app = ObjectProperty()
    _touch = ObjectProperty(None, allownone=True)
    portaling = BoundedNumericProperty(0, min=0, max=2)
    playspeed = BoundedNumericProperty(0, min=-0.999, max=0.999)

    def handle_adbut(self, charsheet, i):
        adder = CharSheetAdder(charsheet=charsheet, insertion_point=i)
        adder.open()

    def draw_arrow(self, *args):
        # Sometimes this gets triggered, *just before* getting
        # unbound, and ends up running one last time *just after*
        # self.dummyspot = None
        if self._touch is None:
            return
        (ox, oy) = self._touch.ud['spot'].pos
        (dx, dy) = self._touch.ud['portaling']['dummyspot'].pos
        (ow, oh) = self._touch.ud['spot'].size
        orx = ow / 2
        ory = oh / 2
        points = get_points(ox, orx, oy, ory, dx, 0, dy, 0, 10)
        self._touch.ud['portaling']['dummyarrow'].canvas.clear()
        with self._touch.ud['portaling']['dummyarrow'].canvas:
            Color(0.25, 0.25, 0.25)
            Line(width=1.4, points=points)
            Color(1, 1, 1)
            Line(width=1, points=points)

    def make_arrow(self, *args):
        _ = self.app.closet.get_text
        self.display_prompt(_(
            "Draw a line between the spots to connect with a portal."))
        self.portaling = 1

    def on_touch_down(self, touch):
        self.ids.board.on_touch_down(touch)
        if self.portaling == 1:
            if "spot" in touch.ud:
                ud = {
                    'dummyspot': Widget(
                        pos=touch.pos),
                    'dummyarrow': TouchlessWidget()}
                self.ids.board.arrowlayout.add_widget(ud['dummyarrow'])
                self.add_widget(ud['dummyspot'])
                ud["dummyspot"].bind(pos=self.draw_arrow)
                touch.ud['portaling'] = ud
                self._touch = touch
                self.portaling = 2
            else:
                self.portaling = 0
                if (
                        'portaling' in touch.ud and
                        'dummyspot' in touch.ud['portaling']):
                    ud = touch.ud['portaling']
                    ud['dummyspot'].unbind(pos=self.draw_arrow)
                    self.remove_widget(ud['dummyspot'])
                    ud['dummyarrow'].canvas.clear()
                    self.ids.board.arrowlayout.remove_widget(
                        ud['dummyarrow'])
                    del touch.ud['portaling']
                self.dismiss_prompt()
                self.origspot = None
                self.dummyspot = None
                self.dummyarrow = None
        return super(LiSELayout, self).on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.portaling == 2:
            self.portaling = 0
            if touch != self._touch:
                return
            ud = touch.ud['portaling']
            ud['dummyspot'].unbind(pos=self.draw_arrow)
            ud['dummyarrow'].canvas.clear()
            self.remove_widget(ud['dummyspot'])
            self.ids.board.remove_widget(ud['dummyarrow'])
            self.dismiss_prompt()
            destspot = None
            for spot in self.ids.board.spotdict.itervalues():
                if spot.collide_point(touch.x, touch.y):
                    destspot = spot
                    break
            if destspot is None:
                ud['dummyarrow'].canvas.clear()
                self.dismiss_prompt()
                return True
            origplace = touch.ud['spot'].place
            destplace = destspot.place
            portalname = "{}->{}".format(origplace, destplace)
            portal = self.ids.board.facade.observed.make_portal(
                portalname, origplace, destplace,
                host=self.ids.board.host)
            arrow = Arrow(
                board=self.ids.board, portal=portal)
            self.ids.board.arrowdict[unicode(portal)] = arrow
            self.ids.board.arrowlayout.add_widget(arrow)
        else:
            return super(LiSELayout, self).on_touch_up(touch)

    def display_prompt(self, text):
        """Put the text in the cue card"""
        self.ids.prompt.ids.l.text = text

    def dismiss_prompt(self, *args):
        """Blank out the cue card"""
        self.ids.prompt.text = ''

    def show_spot_menu(self):
        hostn = unicode(self.ids.board.host)
        if hostn not in self.app.closet.skeleton[u"place"]:
            self.app.closet.skeleton[u"place"][hostn] = {}
        spot_menu_content = SpotMenuContent(
            closet=self.app.closet,
            skel=self.app.closet.skeleton[u"place"][hostn])
        spot_menu = Popup(
            title="Give your place a name and appearance",
            content=spot_menu_content)

        def confirm():
            if spot_menu_content.aggregate():
                spotpicker_args = spot_menu_content.picker_args
                spot_menu_content.selection = []
                spot_menu.dismiss()
                self.show_spot_picker(*spotpicker_args)
        spot_menu_content.confirm = confirm

        def cancel():
            spot_menu_content.selection = []
            spot_menu.dismiss()
        spot_menu_content.cancel = cancel
        spot_menu.open()

    def show_pawn_menu(self):
        obsrvd = unicode(self.ids.board.facade.observed)
        if obsrvd not in self.app.closet.skeleton[u"thing"]:
            self.app.closet.skeleton[u"thing"][obsrvd] = {}
        if obsrvd not in self.app.closet.skeleton[u"thing_loc"]:
            self.app.closet.skeleton[u"thing_loc"][obsrvd] = {}
        pawn_menu_content = PawnMenuContent(
            closet=self.app.closet,
            skel=self.app.closet.skeleton[u"thing"][obsrvd])
        pawn_menu = Popup(
            title="Give this thing a name and appearance",
            content=pawn_menu_content)

        def confirm():
            if pawn_menu_content.aggregate():
                pawnpicker_args = pawn_menu_content.picker_args
                pawn_menu_content.selection = []
                self.show_pawn_picker(*pawnpicker_args)
                pawn_menu.dismiss()
        pawn_menu_content.confirm = confirm

        def cancel():
            pawn_menu_content.selection = []
            pawn_menu.dismiss()
        pawn_menu_content.cancel = cancel
        pawn_menu.open()

    def new_spot_with_name_and_imgs(self, name, imgs):
        _ = self.app.closet.get_text
        if len(imgs) < 1:
            return
        self.display_prompt(_('Drag this place where you want it.'))
        Clock.schedule_once(self.dismiss_prompt, 5)
        place = self.ids.board.host.make_place(name)
        branch = self.app.closet.branch
        tick = self.app.closet.tick
        obsrvr = unicode(self.ids.board.facade.observer)
        host = unicode(self.ids.board.host)
        placen = unicode(place)
        i = 0
        for img in imgs:
            bone = Spot.bonetype(
                observer=obsrvr,
                host=host,
                place=placen,
                layer=i,
                branch=branch,
                tick=tick,
                img=img.name)
            self.app.closet.set_bone(bone)
            i += 1
        (x, y) = self.center_of_view_on_board()
        coord_bone = Spot.bonetypes["spot_coords"](
            observer=obsrvr,
            host=host,
            place=placen,
            branch=branch,
            tick=tick,
            x=int(x), y=int(y))
        self.app.closet.set_bone(coord_bone)
        assert(self.app.closet.have_place_bone(
            host, placen))
        spot = Spot(board=self.ids.board, place=place)
        self.ids.board.spotlayout.add_widget(spot)

    def center_of_view_on_board(self):
        # get the point on the board that is presently at the center
        # of the screen
        b = self.ids.board
        bv = self.ids.board_view
        # clamp to that part of the board where the view's center might be
        effective_w = b.width - bv.width
        effective_h = b.height - bv.height
        x = b.width / 2 + effective_w * (bv.scroll_x - 0.5)
        y = b.height / 2 + effective_h * (bv.scroll_y - 0.5)
        return (x, y)

    def new_pawn_with_name_and_imgs(self, name, imgs):
        """Given some iterable of Swatch widgets, make a dummy pawn, prompt
the user to place it, and dismiss the popup."""
        _ = self.app.closet.get_text
        if len(imgs) < 1:
            return
        self.display_prompt(_(
            'Drag this thing to the spot where you want it.'))
        dummy = DummyPawn(
            name=name,
            closet=self.app.closet,
            board=self.ids.board, bones=imgs)

        def cb():
            self.remove_widget(dummy)
            self.dismiss_prompt()
        dummy.callback = cb
        self.add_widget(dummy)
        (w, h) = self.size
        dummy.pos = (w/2, h/2)

    def show_spot_picker(self, name, imagery):
        def set_imgs(swatches, dialog):
            self.new_spot_with_name_and_imgs(name, [
                swatch.img for swatch in swatches])
            dialog.dismiss()
        if isinstance(imagery, list):
            dialog = PickImgDialog(name=name)
            dialog.set_imgs = lambda swatches: set_imgs(swatches, dialog)
            catimg_d = {}
            for cat in imagery:
                catimg_d[cat] = self.app.closet.imgs_with_tag(
                    cat.strip("?!"))
            dialog.ids.picker.closet = self.app.closet
            dialog.ids.picker.categorized_images = [
                (cat, sorted(images)) for (cat, images) in
                catimg_d.iteritems()]
            popup = Popup(
                title="Select graphics",
                content=dialog,
                size_hint=(0.9, 0.9))
            dialog.cancel = lambda: popup.dismiss()
            popup.open()
        else:
            self.new_spot_with_name_and_imgs(name, [imagery])

    def show_pawn_picker(self, name, imagery):
        """Show a SwatchBox for the given tags. The chosen Swatches will be
        used to build a Pawn later.

        """
        if isinstance(imagery, list):
            pickest = Popup(
                title="Select some images",
                size_hint=(0.9, 0.9))

            def set_imgs(swatches):
                self.new_pawn_with_name_and_imgs(name, [
                    swatch.img for swatch in swatches])
                pickest.dismiss()

            catimglst = [
                (cat, sorted(self.app.closet.image_tag_d[cat]))
                for cat in imagery]
            dialog = PickImgDialog(
                name=name,
                categorized_images=catimglst,
                set_imgs=set_imgs,
                cancel=pickest.dismiss)
            dialog.ids.picker.closet = self.app.closet
            pickest.content = dialog
            pickest.open()
        else:
            img = self.app.closet.skeleton[u"img"][imagery]
            self.new_pawn_with_name_and_imgs(name, [img])

    def normal_speed(self, forward=True):
        if forward:
            self.playspeed = 0.1
        else:
            self.playspeed = -0.1

    def pause(self):
        if hasattr(self, 'updater'):
            Clock.unschedule(self.updater)

    def update(self, ticks):
        try:
            self.app.closet.time_travel_inc_tick(ticks)
        except TimestreamException:
            self.pause()

    def on_playspeed(self, i, v):
        self.pause()
        if v > 0:
            ticks = 1
            interval = v
        elif v < 0:
            ticks = -1
            interval = -v
        else:
            return
        self.updater = lambda dt: self.update(ticks)
        Clock.schedule_interval(self.updater, interval)

    def go_to_branch(self, bstr):
        self.app.closet.time_travel(int(bstr), self.app.closet.tick)

    def go_to_tick(self, tstr):
        self.app.closet.time_travel(self.app.closet.branch, int(tstr))


class LoadImgDialog(FloatLayout):
    """Dialog for adding img files to the database."""
    load = ObjectProperty()
    cancel = ObjectProperty()


class PickImgDialog(FloatLayout):
    """Dialog for associating imgs with something, perhaps a Pawn.

In lise.kv this is given a SwatchBox with texdict=root.texdict."""
    categorized_images = ObjectProperty()
    set_imgs = ObjectProperty()
    cancel = ObjectProperty()


class LiSEApp(App):
    closet = ObjectProperty(None)
    dbfn = StringProperty(allownone=True)
    lgettext = ObjectProperty(None)
    observer_name = StringProperty()
    observed_name = StringProperty()
    host_name = StringProperty()

    def build(self):
        """Make sure I can use the database, create the tables as needed, and
        return the root widget."""
        if self.dbfn is None:
            self.dbfn = self.user_data_dir + sep + "default.lise"
            print("No database specified; defaulting to {}".format(self.dbfn))
        try:
            conn = connect(self.dbfn)
            for tab in tabclas.iterkeys():
                conn.execute("SELECT * FROM {};".format(tab))
        except (IOError, OperationalError):
            mkdb(self.dbfn, __path__[-1])
        self.closet = load_closet(
            self.dbfn, self.lgettext, True)
        self.closet.load_img_metadata()
        self.closet.load_imgs_tagged(['base', 'body'])
        # Currently the decision of when and whether to update things
        # is split between here and the closet. Seems inappropriate.
        self.closet.load_characters([
            self.observer_name,
            self.observed_name,
            self.host_name])
        Clock.schedule_once(lambda dt: self.closet.checkpoint(), 0)
        self.closet.load_charsheet(self.observed_name)
        l = LiSELayout(app=self, board=self.closet.load_board(
            self.observer_name,
            self.observed_name,
            self.host_name))
        from kivy.core.window import Window
        from kivy.modules import inspector
        inspector.create_inspector(Window, l)
        return l

    def on_pause(self):
        self.closet.save()

    def stop(self, *largs):
        self.closet.save_game()
        self.closet.end_game()
        super(LiSEApp, self).stop(*largs)
