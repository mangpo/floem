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

void settings_init(char *argv[])
{
  settings.udpport = 11211;
  settings.verbose = 1;
  settings.segsize = 2048; // 2048
  settings.segmaxnum = 512;
  settings.segcqsize = 8 * 1024;
  struct ip_addr ip = { .addr = {0x0a, 0x03, 0x00, 0x23} };  // n35
  settings.localip = ip;
}

iokvs_message template = {
  .ether = { .type = 0x0008 },
  .ipv4 = { ._v_hl = 0x45, ._ttl = 0x40, ._proto = 0x11},
  .mcudp = { .n_data = 0x0100 }
};

iokvs_message* iokvs_template() {
  return &template;
}

iokvs_message* random_get_request(uint8_t v, uint8_t id) {
  uint16_t keylen = (v % 4) + 1;
  uint16_t extlen = 4;

  iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + extlen + keylen);
  m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
  m->mcr.request.magic = id; // PROTOCOL_BINARY_REQ
  m->mcr.request.opaque = id; // PROTOCOL_BINARY_REQ
  m->mcr.request.keylen = keylen;
  m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
  m->mcr.request.status = 0;

  m->mcr.request.extlen = extlen;
  m->mcr.request.bodylen = extlen + keylen;
  *((uint32_t *)m->payload) = 0;

  uint8_t* key = m->payload + extlen;
  for(size_t i=0; i<keylen; i++)
    key[i] = v;

  return m;
}

iokvs_message* random_set_request(uint8_t v, uint8_t id) {
  uint16_t keylen = (v % 4) + 1;
  uint16_t vallen = (v % 4) + 1;
  uint16_t extlen = 4;

  iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + extlen + keylen + vallen);
  m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
  m->mcr.request.magic = id;
  m->mcr.request.opaque = id;
  m->mcr.request.keylen = keylen;
  m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
  m->mcr.request.status = 0;

  m->mcr.request.extlen = extlen;
  m->mcr.request.bodylen = extlen + keylen + vallen;
  *((uint32_t *)m->payload) = 0;

  uint8_t* key = m->payload + extlen;
  for(size_t i=0; i<keylen; i++)
    key[i] = v;

  uint8_t* val = m->payload + extlen + keylen;
  for(size_t i=0; i<vallen; i++)
    val[i] = v * 3;

  return m;
}

iokvs_message* random_request(uint8_t v) {
    if(v % 2 == 0)
        return random_set_request(v/2, v);
    else
        return random_get_request(v/2, v);
}

iokvs_message* double_set_request(uint8_t v) {
    if(v < 100)
        return random_set_request(v, v);
    else
        return random_set_request(v - 100, v - 100);
}