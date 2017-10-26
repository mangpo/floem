#include <stdlib.h>
#include <stdio.h>
#include <arpa/inet.h>

#include "iokvs.h"

struct settings settings;

void settings_init(char *argv[])
{
  settings.udpport = 11211;
  settings.verbose = 1;
  settings.segsize = 2 * 1024 * 1024; // 2048
  settings.segmaxnum = 512;
  settings.segcqsize = 8 * 1024;
  struct ip_addr ip = { .addr = {0x0a, 0x03, 0x00, 0x23} };  // n35
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

iokvs_message* get_packet(int size) {
  iokvs_message *m = (iokvs_message *) malloc(size);
  m->ether.type = htons(ETHERTYPE_IPv4);
  m->ipv4._proto = 17;
  m->ipv4.dest = settings.localip;
  m->udp.dest_port = htons(11211);
  return m;
}

iokvs_message* random_get_request(uint8_t v, uint8_t id) {
  uint16_t keylen = (v % 4) + 1;
  uint16_t extlen = 4;

  printf("get: v = %d, id = %d\n", v, id);

  iokvs_message *m = get_packet(sizeof(iokvs_message) + extlen + keylen);
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
  uint16_t i;
  for(i=0; i<keylen; i++)
    key[i] = v;

  return m;
}

iokvs_message* random_set_request(uint8_t v, uint8_t id) {
  uint16_t keylen = (v % 4) + 1;
  uint16_t vallen = (v % 4) + 1;
  uint16_t extlen = 4;
  printf("set: v = %d, id = %d\n", v, id);


  iokvs_message *m = get_packet(sizeof(iokvs_message) + extlen + keylen + vallen);
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
  uint16_t i;
  for(i=0; i<keylen; i++)
    key[i] = v;

  uint8_t* val = m->payload + extlen + keylen;
  for(i=0; i<vallen; i++)
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
