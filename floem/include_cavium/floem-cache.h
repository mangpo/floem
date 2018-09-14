#ifndef CACHE_H
#define CACHE_H

#include <cvmx-atomic.h>
#include "cvmcs-nic.h"
#include "floem-util.h"

//#define DEBUG
#define HIT_RATE
#define BUCKET_NITEMS 1

typedef struct _cache_bucket cache_bucket;

typedef struct _citem {
    struct _citem* next;
    cache_bucket* bucket;
    uint32_t hv;
    uint16_t keylen, last_vallen;
    uint8_t evicted;
    uint8_t content[];
} __attribute__((packed)) citem;

typedef struct _cache_bucket {
    citem *items[BUCKET_NITEMS];
    uint32_t hashes[BUCKET_NITEMS];
    lock_t lock;
    int replace;
} __attribute__((packed)) cache_bucket;

inline bool citem_key_matches(citem *it, const void *key, int klen);
inline bool citem_hkey_matches(citem *it, const void *key, int klen, uint32_t hv);
inline void *citem_key(citem *it);
inline void *citem_value(citem *it);
void cache_init(cache_bucket *buckets, int n);
citem *cache_get(cache_bucket *buckets, int nbuckets, const void *key, int klen, uint32_t hv);
citem *cache_put(cache_bucket *buckets, int nbuckets, citem *nit, bool replace);
citem *cache_put_or_get(cache_bucket *buckets, int nbuckets, citem *nit, bool replace);
void cache_delete(cache_bucket *buckets, int nbuckets, void* key, int klen, uint32_t hv);
uint32_t jenkins_hash(const void *key, size_t length);

#endif
