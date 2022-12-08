#!/bin/sh

docker run --rm --privileged -it -e "TERM=xterm-256color" ramulator-pim bash -l

#Saving state:
#docker commit container_name ramulator-pim
