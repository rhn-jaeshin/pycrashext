#!/bin/bash

usage() {
	echo 
	echo "To run this server as a standalone, you need to have"
	echo "the below commands installed."
	echo
	echo "python"
	echo "virtualenv"
	echo "pip"
	echo
}

if [ -z $RHEL_SOURCE_DIR ] || [ $RHEL_SOURCE_DIR == "" ]; then
	echo "RHEL_SOURCE_DIR bash variable should be configured"
	echo "and should point to the source directory."
	echo
	echo "  example)  export RHEL_SOURCE_DIR='/home/dkwon/source/'"
	echo
	echo "The source tree should be something like below."
	echo
	echo "<your_source_dir> -+-- rhel5"
	echo "                   +-- rhel6"
        echo "                   ..."
        echo "                   +-- fedora"
	echo
	echo "The directory doesn't need to have all source repositories."
	echo "It only needs to have the directories you are going to use."
	echo
	exit -1
fi

cd web
virtualenv .  >/dev/null 2>&1 || { usage; exit -2; }
source bin/activate
pip install -r requirements.txt  >/dev/null 2>&1 || { usage; exit -3; }

python app.py || { usage; exit -4; }
