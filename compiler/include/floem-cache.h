#ifndef CACHE_H
#define CACHE_H

#include <cvmx-atomic.h>
#include "cvmcs-nic.h"
#include "floem-util.h"

//#define DEBUG
#define HIT_RATE
#define BUCKET_NITEMS 5

typedef struct _cache_bucket cache_bucket;

typedef struct _citem {
    struct _citem* next;
    cache_bucket* bucket;
    uint32_t hv;
    uint16_t keylen, last_vallen;
    uint8_t evicted;
    uint8_t content[];
} citem;

typedef struct _cache_bucket {
    lock_t lock;
    int replace;
    citem *items[BUCKET_NITEMS];
    uint32_t hashes[BUCKET_NITEMS];
} CVMX_CACHE_LINE_ALIGNED cache_bucket;

inline bool citem_key_matches(citem *it, const void *key, int klen);
inline bool citem_hkey_matches(citem *it, const void *key, int klen, uint32_t hv);
inline void *citem_key(citem *it);
inline void *citem_value(citem *it);
void cache_init(cache_bucket *buckets, int n);
citem *cache_get(cache_bucket *buckets, int nbuckets, const void *key, int klen, uint32_t hv, bool* success);
citem *cache_put(cache_bucket *buckets, int nbuckets, citem *nit, bool replace, bool* success);
citem *cache_put_or_get(cache_bucket *buckets, int nbuckets, citem *nit, bool replace, bool* success);
void cache_delete(cache_bucket *buckets, int nbuckets, void* key, int klen, uint32_t hv, bool* success);
inline void cache_release(citem *it);
uint32_t jenkins_hash(const void *key, size_t length);


void cache_info(cache_bucket *buckets, int nbuckets, uint32_t hv, const char*);

#endif
