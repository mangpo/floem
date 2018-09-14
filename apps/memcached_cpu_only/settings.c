#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <arpa/inet.h>

#include "iokvs.h"

struct settings settings;

void settings_init(int argc, char *argv[])
{
  settings.udpport = 11211;
  settings.verbose = 1;
  settings.segsize = 2 * 1024 * 1024; // debug: 2048, real: 2MB
  settings.segmaxnum = 512;
  settings.segcqsize = 8 * 1024;

  if (argc != 2) {
    fprintf(stderr, "Usage: flexkvs LOCAL-IP LOCAL-MAC\n");
    exit(1);
  }

#ifdef RTE
  if (inet_pton(AF_INET, argv[1], &settings.localip) != 1) {
    fprintf(stderr, "Parsing ip failed\n");
    exit(1);
  }
#else
    struct ip_addr ip = { .addr = {0x0, 0x0, 0x0, 0x0} };
    settings.localip = ip;
#endif

}

