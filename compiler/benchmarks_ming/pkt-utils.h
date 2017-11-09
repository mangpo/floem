/*
 * Packet utilities header
 */
#ifndef _PKT_UTILS_H
#define _PKT_UTILS_H
#include <stdint.h>
#include <stdbool.h>

#define CAVIUM
#define UDP_PAYLOAD 42

uint32_t get_flow_id(uint8_t *pkt_ptr);
void print_pkt(uint8_t *pkt_ptr, int len);
bool pkt_filter(uint8_t *pkt_ptr);
void header_swap(uint8_t *pkt_ptr);

#endif /* _PKT_UTILS_H */
