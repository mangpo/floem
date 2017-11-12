#include <stdlib.h>
#include <stdio.h>
#include <arpa/inet.h>

#include "iokvs.h"

CVMX_SHARED struct settings settings;

void settings_init()
{
  settings.udpport = 11211;
  settings.verbose = 1;
  settings.segsize = 2 * 1024 * 1024; // debug: 2048, real: 2MB
  settings.segmaxnum = 128;
  settings.segcqsize = 8 * 1024;
  settings.localip = "\x0a\x03\x00\x23"; // n35
}

uint32_t settings_total_space() {
    return settings.segsize * settings.segmaxnum;
}