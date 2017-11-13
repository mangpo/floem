#include "cvmx.h"
#include "cvmx-atomic.h"
#include "shared-mm.h"
#include "util.h"
#include "iokvs.h"

struct settings settings;

void settings_init()
{
  settings.udpport = 11211;
  settings.verbose = 1;
  settings.segsize = 2 * 1024 * 1024; // debug: 2048, real: 2MB
  settings.segmaxnum = 128;
  settings.segcqsize = 8 * 1024;
  struct ip_addr ip = { .addr = {0x0a, 0x03, 0x00, 0x23} }; 
  settings.localip = ip;
}

