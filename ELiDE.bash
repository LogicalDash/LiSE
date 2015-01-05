#!/bin/bash
if [ -z "$LISE_PATH" ]; then
    LISE_PATH="`dirname "$0"`/LiSE";
fi;

GUITERM=" "
# GUITERM="`which konsole` ";
# if [ "$GUITERM" == " " ]; then
#     GUITERM="`which gnome-terminal` ";
# fi;
# if [ "$GUITERM" == " " ]; then
#     GUITERM="`which xterm` ";
# fi;
# if [ "$GUITERM" == " " ]; then
#     echo "Couldn't get a graphical terminal emulator."
#     echo "I'll try to use your current terminal..."
# fi;

if [ -e "$LISE_PATH" ] && [ -f "$LISE_PATH/.installed" ]; then
    cd "$LISE_PATH";
    git pull;
    git submodule update;
    python3 setup.py install --user --upgrade;
    python3 -m ELiDE;
else
    if [ -e "$LISE_PATH" ]; then
        # clean out failed installation
        rm -rf "$LISE_PATH";
    fi;

    PKGINST='echo "About to install dependencies." && sudo add-apt-repository -y ppa:thopiekar/pygame && sudo add-apt-repository -y ppa:kivy-team/kivy-daily &&ssudo apt-get -y update && sudo apt-get -y install git cython3 python3-setuptools python3-kivy python3-numpy;'

    if [ "$GUITERM" == " " ]; then
        echo $PKGINST | bash -si
    else
        PKGINST="$GUITERM-e $PKGINST";
        echo "executing $PKGINST";
        $PKGINST
    fi;

    exit;

    cd "`dirname "$0"`";
    git clone https://github.com/LogicalDash/LiSE.git;
    cd LiSE;
    git submodule init;
    git submodule update;
    python3 setup.py install --user;

    echo "[Desktop Entry]
Comment=Development environment for LiSE
Exec=\"`dirname \"$0\"`/ELiDE\"
Name=ELiDE
Type=Application
Categories=Development;
" >$HOME/.local/share/applications/ELiDE.desktop;
    xdg-desktop-menu forceupdate;

    touch "$LISE_PATH/.installed";

    python3 -m ELiDE;
fi
