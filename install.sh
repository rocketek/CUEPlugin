#!/bin/bash
src=$(dirname $0)
install_dir="$HOME/.local/share/rhythmbox/plugins/cue_plugin"

if [ -e "$src/cue_plugin.plugin" ]; then
    sed 's/^Description=//;t;d' "$src/cue_plugin.plugin";
    echo 
    echo "Installing plugin to: $install_dir";
    echo
else
   echo "Couldn't find plugin file"
fi

mkdir -p $install_dir;
cp $src/cue_plugin.plugin $install_dir
cp $src/cue_plugin.py $install_dir
echo "RESTART Rhythmbox, installation done."
echo "You need to  enable the plugin in 'Preferences->Plugins->CUE Plugin'"
