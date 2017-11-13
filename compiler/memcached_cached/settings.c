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

iokvs_message template = {
  .ipv4 = { ._v_hl = 0x45, ._ttl = 0x40, ._proto = 0x11},
#ifndef CAVIUM
  .ether = { .type = 0x0008 },
  .mcudp = { .n_data = 0x0100 }
#else
  .ether = { .type = 0x0800 },
  .mcudp = { .n_data = 1 }
#endif
}; // CAVIUM

iokvs_message* iokvs_template() {
  return &template;
}