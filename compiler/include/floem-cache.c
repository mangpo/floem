#include "global-config.h"
#include "octeon-pci-console.h"
#include "cvmcs-common.h"
#include "cvmcs-nic.h"
#include  <cvmx-atomic.h>
#include  <cvmx-access.h>
#include  <cvmx-fau.h>
#include "cvmcs-nic-tunnel.h"
#include "cvmcs-nic-rss.h"
#include "cvmcs-nic-ipv6.h"
#include "cvmcs-nic-ether.h"
#include "cvmcs-nic-mdata.h"
#include "cvmcs-nic-switch.h"
#include "cvmcs-nic-printf.h"
#include "cvm-nic-ipsec.h"
#include "nvme.h"
#include <errno.h>
#include "cvmcs-nic-fwdump.h"
#include "cvmcs-nic-component.h"
#include "cvmcs-nic-hybrid.h"
#include "cvmcs-dcb.h"
#include "generated/cvmcs-nic-version.h"
#include "floem-util.h"
#include "floem-cache.h"


inline bool citem_key_matches(citem *it, const void *key, int klen)
{
    return klen == it->keylen && !__builtin_memcmp(it->content, key, klen);
}

inline bool citem_hkey_matches(citem *it, const void *key, int klen, uint32_t hv)
{
  //printf("hkey_matches: %d %d %d\n", it->hv == hv, klen == it->keylen, !__builtin_memcmp(it->content, key, klen));
  //printf("hash: %d %d %d %d\n", it->hv, hv, klen, it->keylen);
    return it->hv == hv && citem_key_matches(it, key, klen);
}

inline void *citem_key(citem *it) {
    return it->content;
}

inline void *citem_value(citem *it) {
    uint8_t *p = it->content;
    return (p + it->keylen);
}

void cache_init(cache_bucket *buckets, int n)
{
  int i;
  for (i = 0; i < n; i++) {
    lock_init(&buckets[i].lock);
    buckets[i].replace = 0;
  }
}

void cache_info(cache_bucket *buckets, int nbuckets, uint32_t hv, const char* s) {
  cache_bucket *b = buckets + (hv % nbuckets);
  citem *it = b->items[0];
  if(it)
    printf(">>> cache_info (%s): it = %p, hv = %d, klen = %d, next = %p\n", s, it, it->hv, it->keylen, it->next);
}

#define TRY 10
citem *cache_get(cache_bucket *buckets, int nbuckets, const void *key, int klen, uint32_t hv, bool* success)
{
#ifdef DEBUG
    printf("cache_get_begin: key = %d, hash = %d\n", *((int*) key), hv);
#endif

#ifdef HIT_RATE
    static __thread size_t hit = 0, total = 0;
    total++;
#endif

    citem *it = NULL;
    size_t i;

    cache_bucket *b = buckets + (hv % nbuckets);
    
    /*
    //if(cvmx_spinlock_locked(&b->lock)) {
    if(cvmx_spinlock_trylock(&b->lock)) { 
      *success = false;
      return NULL;
    }
    
    lock_lock(&b->lock);
    *success = true;
    */
    
    int count = 0;
    while(cvmx_spinlock_trylock(&b->lock)) {
      count++;
      if(count == TRY) {
	*success = false;
	return NULL;
      }
    }
    *success = true;
    

    for (i = 0; i < BUCKET_NITEMS; i++) {
        if (b->items[i] != NULL && b->hashes[i] == hv) {
            it = b->items[i];
            if (citem_key_matches(it, key, klen)) {
                goto done;
            }
        }
    }
    it = b->items[BUCKET_NITEMS - 1];
    if (it != NULL) {
        it = it->next;
	/*
	assert(it == NULL);
        while (it != NULL && !citem_hkey_matches(it, key, klen, hv)) {
            it = it->next;
        }
	*/
    }

done:
#ifdef DEBUG
    printf("cache_get: key = %d, hash = %d, it = %p\n", *((int*) key), hv, it);
#endif
    if(it == NULL)
        lock_unlock(&b->lock);

#ifdef HIT_RATE
    if(it) hit++;
    if(total == 1000000) {
      printf("hit rate = %f\n", 1.0*hit/total);
      hit = 0; total = 0;
    }
#endif
    return it;
}


citem *cache_put(cache_bucket *buckets, int nbuckets, citem *nit, bool replace, bool* success)
{
    citem *it, *prev;
    size_t i, di;
    bool has_direct = false;
    uint32_t hv = nit->hv;
    void *key = citem_key(nit);
    size_t klen = nit->keylen;
    nit->evicted = 1;

#ifdef DEBUG
    int *val = citem_value(nit);
    printf("cache_put: hash = %d, key = %d, val = %d, it = %p\n", hv, *((int*) key), *val, nit);
#endif

    cache_bucket *b = buckets + (hv % nbuckets);
    /*
    //if(cvmx_spinlock_locked(&b->lock)) {
    if(cvmx_spinlock_trylock(&b->lock)) { 
      *success = false;
      return NULL;
    }

    //lock_lock(&b->lock);
    *success = true;
    //printf("lock\n");
    */

    int count = 0;
    while(cvmx_spinlock_trylock(&b->lock)) {
      count++;
      if(count == TRY) {
	*success = false;
	return NULL;
      }
    }
    *success = true;
    

    // Check if we need to replace an existing item
    for (i = 0; i < BUCKET_NITEMS; i++) {
        if (b->items[i] == NULL) {
            has_direct = true;
            di = i;
        } else if (b->hashes[i] == hv) {
            it = b->items[i];
            if (citem_key_matches(it, key, klen)) {
                assert(nit != it);
                nit->next = it->next;
                b->items[i] = nit;
#ifdef DEBUG
                printf("free %p\n", it);
#endif
                shared_mm_free(it);
                nit->bucket = b;
                return nit;
            }
        }
    }

    // Note it does not match, otherwise we would have already bailed in the for
    // loop
    it = b->items[BUCKET_NITEMS - 1];
    if (it != NULL) {
        prev = it;
        it = it->next;
	/*
	assert(it == NULL);

        while (it != NULL && !citem_hkey_matches(it, key, klen, hv)) {
            prev = it;
            it = it->next;
        }
	*/
        if (it != NULL) {
            nit->next = it->next;
            prev->next = nit;
#ifdef DEBUG
            printf("free %p\n", it);
#endif
            shared_mm_free(it);
            nit->bucket = b;
            return nit;
        }
    }

    // We did not find an existing entry to replace, just stick it in wherever
    // we find room

    if(has_direct) {
        assert(b->items[di] == NULL);
        nit->next = NULL;
        b->hashes[di] = hv;
        b->items[di] = nit;
        nit->bucket = b;
        return nit;
    }

    if(replace) {
        citem *evict;
        // evict
        di = b->replace;
        b->replace = (b->replace + 1) % BUCKET_NITEMS;
        evict = b->items[di];
	assert(evict != NULL);
        evict->evicted |= 2;
        b->items[di] = NULL;

        nit->next = NULL;
        b->hashes[di] = hv;
        b->items[di] = nit;
        nit->bucket = b;
#ifdef DEBUG
        printf("insert & evict %p , flag = %d\n", evict, evict->evicted);
#endif
        return evict;
    }

    lock_unlock(&b->lock);
#ifdef DEBUG
        printf("insert fail (no replace)\n");
#endif
    return NULL;
}

citem *cache_put_or_get(cache_bucket *buckets, int nbuckets, citem *nit, bool replace, bool* success)
{
    citem *it;
    size_t i, di;
    bool has_direct = false;
    uint32_t hv = nit->hv;
    void *key = citem_key(nit);
    size_t klen = nit->keylen;
    nit->evicted = 0;

#ifdef DEBUG
    int *val = citem_value(nit);
    printf("cache_put_get: hash = %d, key = %d, val = %d, it = %p\n", hv, *((int*) key), *val, nit);
#endif

    cache_bucket *b = buckets + (hv % nbuckets);
    /*
    //if(cvmx_spinlock_locked(&b->lock)) {
    if(cvmx_spinlock_trylock(&b->lock)) { 
      *success = false;
      return NULL;
    }

    //lock_lock(&b->lock);
    *success = true;
    //printf("lock\n");
    */

    int count = 0;
    while(cvmx_spinlock_trylock(&b->lock)) {
      count++;
      if(count == TRY) {
	*success = false;
	return NULL;
      }
    }
    *success = true;
    

    // Check if we need to replace an existing item
    for (i = 0; i < BUCKET_NITEMS; i++) {
        if (b->items[i] == NULL) {
            has_direct = true;
            di = i;
        } else if (b->hashes[i] == hv) {
            it = b->items[i];
            if (citem_key_matches(it, key, klen)) {
                if(nit == it) printf("assert fail: nit = %p, it = %p\n", nit, it);
                assert(nit != it);
                //nit->next = it->next;
                //b->items[i] = nit;
#ifdef DEBUG
                printf("exist %p\n", it);
#endif
                shared_mm_free(nit);
                return it;
            }
        }
    }

    // Note it does not match, otherwise we would have already bailed in the for
    // loop
    it = b->items[BUCKET_NITEMS - 1];
    if (it != NULL) {
      //prev = it;
        it = it->next;
	/*
	assert(it == NULL);

        while (it != NULL && !citem_hkey_matches(it, key, klen, hv)) {
	  //prev = it;
            it = it->next;
        }
	*/

        if (it != NULL) {
            //nit->next = it->next;
            //prev->next = nit;
#ifdef DEBUG
            printf("exist %p\n", it);
#endif
            shared_mm_free(nit);
            return it; // need to release later
        }
    }

    // We did not find an existing entry to replace, just stick it in wherever
    // we find room
    if(has_direct) {
        assert(b->items[di] == NULL);
        nit->next = NULL;
        b->hashes[di] = hv;
        b->items[di] = nit;
        nit->bucket = b;
        lock_unlock(&b->lock);
#ifdef DEBUG
        printf("insert success %p\n", nit);
#endif
        return NULL;
    }

    if(replace) {
        citem *evict;
        // evict
        di = b->replace;
        b->replace = (b->replace + 1) % BUCKET_NITEMS;
        evict = b->items[di];
	assert(evict != NULL);
        evict->evicted |= 2;
        b->items[di] = NULL;

        nit->next = NULL;
        b->hashes[di] = hv;
        b->items[di] = nit;
        nit->bucket = b;
        //lock_unlock(&b->lock);
#ifdef DEBUG
        printf("insert & evict %p , flag = %d\n", evict, evict->evicted);
#endif
        return evict;
    }

    lock_unlock(&b->lock);
#ifdef DEBUG
    printf("insert fail %p\n", nit);
#endif
    return NULL;
}

void cache_delete(cache_bucket *buckets, int nbuckets, void* key, int klen, uint32_t hv, bool* success)
{
    citem *it, *prev;
    size_t i;

#ifdef DEBUG
    printf("cache_delete: hash = %d, key = %d\n", hv, *((int*) key));
#endif

    cache_bucket *b = buckets + (hv % nbuckets);
    /*
    //if(cvmx_spinlock_locked(&b->lock)) {
    if(cvmx_spinlock_trylock(&b->lock)) { 
      *success = false;
      return;
    }

    //lock_lock(&b->lock);
    *success = true;
    //printf("lock\n");
    */

    int count = 0;
    while(cvmx_spinlock_trylock(&b->lock)) {
      count++;
      if(count == TRY) {
	*success = false;
	return;
      }
    }
    *success = true;
    

    // Check if we need to replace an existing item
    for (i = 0; i < BUCKET_NITEMS; i++) {
        if (b->items[i] && b->hashes[i] == hv) {
            it = b->items[i];
            if (citem_key_matches(it, key, klen)) {
                b->items[i] = it->next;
                if(b->items[i]) b->hashes[i] = b->items[i]->hv;
                shared_mm_free(it);
                goto done;
            }
        }
    }

    // Note it does not match, otherwise we would have already bailed in the for
    // loop
    it = b->items[BUCKET_NITEMS - 1];
    if (it != NULL) {
        prev = it;
        it = it->next;
	/*
	assert(it == NULL);

        while (it != NULL && !citem_hkey_matches(it, key, klen, hv)) {
            prev = it;
            it = it->next;
        }
	*/
        if (it != NULL) {
            prev->next = it->next;
            shared_mm_free(it);
            goto done;
        }
    }


done:
    lock_unlock(&b->lock);
}

inline void cache_release(citem *it) {
    if(it) {
        //printf("unlock %p\n", it);
        lock_unlock(&it->bucket->lock);
        //printf("unlock done %p\n", it);
    }
}
