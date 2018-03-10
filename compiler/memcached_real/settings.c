#include <stdlib.h>
#include <stdio.h>
#include <arpa/inet.h>

#include "iokvs.h"

struct settings settings;

int parse_mac(char *arg, uint64_t *out)
{
    int i;
    uint64_t x, y;
    if (strlen(arg) != 17 || arg[2] != ':' || arg[5] != ':' ||
        arg[8] != ':' || arg[11] != ':' || arg[14] != ':')
    {
        return -1;
    }

    y = 0;
    arg[2] = arg[5] = arg[8] = arg[11] = arg[14] = 0;
    for (i = 5; i >= 0; i--) {
        if (!isxdigit(arg[3 * i]) || !isxdigit(arg[3 * i + 1])) {
            return -1;
        }
        x = strtoul(&arg[3 * i], NULL, 16);
        y = (y << 8) | x;
    }
    *out = y;

    return 0;
}

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

