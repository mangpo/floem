#ifndef CACHE_H
#define CACHE_H

#include <stdlib.h>
#include <stdio.h>

#include <rte_spinlock.h>

#define BUCKET_NITEMS 5

typedef struct _hitem {
    htime* next;
    hash_bucket* bucket;
    uint32_t hv;
    uint16_t keylen, last_vallen;
    uint8_t content[];
} __attribute__((packed)) hitem;

typedef struct _hash_bucket {
    hitem *items[BUCKET_NITEMS];
    uint32_t hashes[BUCKET_NITEMS];
    rte_spinlock_t lock;
} __attribute__((packed)) hash_bucket;

static inline bool item_key_matches(hitem *it, const void *key, int klen)
{
    return klen == it->keylen && !__builtin_memcmp(it->content, key, klen);
}

static inline bool item_hkey_matches(hitem *it, const void *key, int klen, uint32_t hv)
{
    return it->hv == hv && item_key_matches(it, key, klen);
}

static inline void *item_key(hitem *it) {
    return it->content;
}

void hasht_init(hash_bucket *buckets, int n)
{
    for (int i = 0; i < n; i++) {
        rte_spinlock_init(&buckets[i].lock);
    }
}

hitem *hasht_get(const void *key, int klen, uint32_t hv)
{
    struct hash_bucket *b;
    hitem *it;
    size_t i;

    b = buckets + (hv % nbuckets);
    rte_spinlock_lock(&b->lock);

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
    //rte_spinlock_unlock(&b->lock);
    return it;
}


void hasht_put(hitem *nit, item *cas)
{
    struct hash_bucket *b;
    item *it, *prev;
    size_t i, di;
    bool has_direct = false;
    uint32_t hv = nit->hv;
    void *key = item_key(nit);
    size_t klen = nit->keylen;


    b = buckets + (hv % nbuckets);
    rte_spinlock_lock(&b->lock);

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
                nit->next = it->next;
                b->items[i] = nit;
                free(it);
                nit->bucket = b;
                goto done;
            }
        }
    }

    if (cas != NULL) {
        goto done;
    }

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
            free(it);
            nit->bucket = b;
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
    nit->bucket = b;

done:
    //rte_spinlock_unlock(&b->lock);
    return;
}

void hasht_release(hitem *it) {
    rte_spinlock_unlock(&it->bucket->lock);
}

uint32_t hash(uint8_t* key, int keylen);

#endif