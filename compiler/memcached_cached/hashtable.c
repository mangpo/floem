#include "iokvs.h"

#ifdef CAVIUM
#include "cvmx.h"
#include "cvmx-atomic.h"
#include "shared-mm.h"
#include "util.h"
#else
#include <stdlib.h>
#include <stdio.h>
#include <dpdkif.h>
#endif

#define HASHTABLE_POWER 15
#define TABLESZ(p) (1ULL << (p))

#define BUCKET_NITEMS 5

//#define NOHTLOCKS 1

struct hash_bucket {
    item *items[BUCKET_NITEMS];
    uint32_t hashes[BUCKET_NITEMS];
    spinlock_t lock;
} CVMX_CACHE_LINE_ALIGNED;

//static_assert(sizeof(struct hash_bucket) == 64, "Bad hash bucket size");

/******************************************************************************/
/* Hashtable */

CVMX_SHARED static size_t nbuckets;
CVMX_SHARED static struct hash_bucket *buckets;

void hasht_init(void)
{
    size_t i;

    nbuckets = TABLESZ(HASHTABLE_POWER);
    buckets = (struct hash_bucket *) shared_mm_malloc((nbuckets + 1) * sizeof(*buckets));
    buckets = (struct hash_bucket *) (((uintptr_t) buckets + 63) & ~63ULL);
    if (buckets == NULL) {
        perror("Allocating item hash table failed");
        abort();
    }

    for (i = 0; i < nbuckets; i++) {
        spinlock_init(&buckets[i].lock);
    }
}


static inline bool item_key_matches(item *it, const void *key,
        size_t klen)
{
    return klen == it->keylen && !__builtin_memcmp(item_key(it), key, klen);
}

static inline bool item_hkey_matches(item *it, const void *key,
        size_t klen, uint32_t hv)
{
    return it->hv == hv && item_key_matches(it, key, klen);
}


item *hasht_get(const void *key, size_t klen, uint32_t hv)
{
    struct hash_bucket *b;
    item *it;
    size_t i;

    b = buckets + (hv % nbuckets);
#ifndef NOHTLOCKS
    spinlock_lock(&b->lock);
#endif

    for (i = 0; i < BUCKET_NITEMS; i++) {
        if (b->items[i] != NULL && b->hashes[i] == hv) {
            it = b->items[i];
            if (item_key_matches(it, key, klen)) {
                goto done;
            }
        }
    }
    it = b->items[BUCKET_NITEMS - 1];
    if (it != NULL) {
        it = it->next;
        while (it != NULL && !item_hkey_matches(it, key, klen, hv)) {
            it = it->next;
        }
    }
done:
    if (it != NULL) {
        item_ref(it);
    }
#ifndef NOHTLOCKS
    spinlock_unlock(&b->lock);
#endif
    return it;
}


void hasht_put(item *nit, item *cas)
{
    struct hash_bucket *b;
    item *it, *prev;
    size_t i, di;
    bool has_direct = false;
    uint32_t hv = nit->hv;
    void *key = item_key(nit);
    size_t klen = nit->keylen;


    b = buckets + (hv % nbuckets);
    di = 0;
#ifndef NOHTLOCKS
    spinlock_lock(&b->lock);
#endif

    // Check if we need to replace an existing item
    for (i = 0; i < BUCKET_NITEMS; i++) {
        if (b->items[i] == NULL) {
            has_direct = true;
            di = i;
        } else if (b->hashes[i] == hv) {
            it = b->items[i];
            if (item_key_matches(it, key, klen)) {
                // Were doing a compare and set
                if (cas != NULL && cas != it) {
                    goto done;
                }
                assert(nit != it);
                item_ref(nit);
                nit->next = it->next;
                b->items[i] = nit;
                item_unref(it);
                goto done;
            }
        }
    }

    if (cas != NULL) {
        goto done;
    }

    item_ref(nit);

    // Note it does not match, otherwise we would have already bailed in the for
    // loop
    it = b->items[BUCKET_NITEMS - 1];
    if (it != NULL) {
        prev = it;
        it = it->next;
        while (it != NULL && !item_hkey_matches(it, key, klen, hv)) {
            prev = it;
            it = it->next;
        }

        if (it != NULL) {
            nit->next = it->next;
            prev->next = nit;
            item_unref(it);
            goto done;
        }
    }

    // We did not find an existing entry to replace, just stick it in wherever
    // we find room
    if (!has_direct) {
        di = BUCKET_NITEMS - 1;
    }
    nit->next = b->items[di];
    b->hashes[di] = hv;
    b->items[di] = nit;

done:
#ifndef NOHTLOCKS
    spinlock_unlock(&b->lock);
#endif
    return;
}
