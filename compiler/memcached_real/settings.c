#include <stdlib.h>
#include <stdio.h>
#include <arpa/inet.h>

#include "iokvs.h"

struct settings settings;

void settings_init(int argc, char *argv[])
{
  settings.udpport = 11211;
  settings.verbose = 1;
  settings.segsize = 2 * 1024 * 1024;
  settings.segmaxnum = 128;
  settings.segcqsize = 8 * 1024;

  if (argc != 2) {
    fprintf(stderr, "Usage: flexkvs LOCAL-IP\n");
    exit(1);
  }

  if (inet_pton(AF_INET, argv[1], &settings.localip) != 1) {
    fprintf(stderr, "Parsing ip failed\n");
    exit(1);
  }
}

