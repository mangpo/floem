#ifndef UTIL_H
#define UTIL_H

#define nic_htons(x) x
#define nic_ntohs(x) x
#define nic_htonl(x) x
#define nic_ntohl(x) x
#define nic_htonp(x) x
#define nic_ntohp(x) x

static inline uint64_t htonp(uint64_t x)
{
  uint8_t *s = (uint8_t *)&x;
  uint64_t ret = (uint64_t)((uint64_t) s[0] << 56 | (uint64_t) s[1] << 48 |
			    (uint64_t) s[2] << 40 | (uint64_t) s[3] << 32 |
			    (uint64_t) s[4] << 24 | (uint64_t) s[5] << 16 |
			    (uint64_t) s[6] << 8 | s[7]);
  //printf("htonp: %p -> %p\n", (void*) x, (void*) ret);
  return ret;
}

static inline uint64_t ntohp(uint64_t x) {
  return htonp(x);
}


// Ignore CAVIUM DEFINE
#define CVMX_CACHE_LINE_ALIGNED
#define CVMX_SHARED

#endif