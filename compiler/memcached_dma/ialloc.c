#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <fcntl.h>

#include <rte_spinlock.h>

#include "iokvs.h"


#define SF_INACTIVE 1
#define SF_NIC 2
#define SF_CLEANED 4

static struct segment_header *free_segments;
static rte_spinlock_t segalloc_lock;
static void *seg_base;
static struct segment_header **seg_headers;
static size_t seg_alloced;

#ifdef BARRELFISH
void *mem_base;
uint64_t mem_base_phys;
#endif

uint64_t get_pointer_offset(void* p) {
    return (uintptr_t) p - (uintptr_t) seg_base;
}

void* get_pointer(uint64_t offset) {
    return (void *) ((uintptr_t) seg_base + offset);
}

void ialloc_init() {
  if ((seg_headers = calloc(settings.segmaxnum, sizeof(*seg_headers))) ==
            NULL)
    {
        perror("Allocating segment header array failed");
        abort();
    }
}

static struct segment_header *segment_alloc(uint32_t core_id)
{
    struct segment_header *h = NULL;
    void *data;
    size_t i, segsz;

    /* Try to get a segment from the freelist */
    if (free_segments != NULL) {
        rte_spinlock_lock(&segalloc_lock);
        if (free_segments != NULL) {
            h = free_segments;
            free_segments = h->next;
        }
        rte_spinlock_unlock(&segalloc_lock);

        if (h != NULL) {
            goto init_h;
        }
    }

    /* Check if there are still unallocated segments (note: unlocked) */
    i = seg_alloced;
    if (i >= settings.segmaxnum) {
        rte_spinlock_unlock(&segalloc_lock);
	printf("i = %d >= settings.segmaxnum (1)\n", i);
	exit(1);
        return NULL;
    }

    /* If there is a possiblity that there are still unallocated segments, let's
     * go for it. */
    rte_spinlock_lock(&segalloc_lock);
    i = seg_alloced;
    if (i >= settings.segmaxnum) {
        rte_spinlock_unlock(&segalloc_lock);
	    printf("i = %d >= settings.segmaxnum (2)\n", i);
	    exit(1);
        return NULL;
    }

    seg_alloced++;
    rte_spinlock_unlock(&segalloc_lock);

    segsz = settings.segsize;

    uint64_t phys;
    size_t size;
    bool success = huge_alloc_phys(&data, &phys, &size);
    if(!success) {
        printf("huge_alloc_phys: failed.\n");
	    exit(1);
        return NULL;
    }

    //data = (void *) ((uintptr_t) seg_base + segsz * i);
    printf("segment alloc: seg_base = %p, data = %p, i = %d\n", seg_base, data, i);
    //#ifndef BARRELFISH
#ifdef BARRELFISH
    if (mprotect(data, settings.segsize, PROT_READ | PROT_WRITE) != 0) {
	    printf("mprotect failed\n");
	    fflush(stdout);
        perror("mprotect failed");
        /* TODO: check what to do here */
        return NULL;
    }
#endif
    fflush(stdout);

    h = malloc(sizeof(*h));
    if (h == NULL) {
        /* TODO: check what to do here */
        return NULL;
    }
    seg_headers[i] = h;

    h->size = segsz;
    h->data = data;
    h->addr = phys;
init_h:
    h->offset = 0;
    h->flags = 0;
    h->freed = 0;
    h->core_id = core_id;
    return h;
}

/*
static inline struct segment_header *segment_from_part(void *data)
{
    size_t i = ((uintptr_t) data - (uintptr_t) seg_base) / settings.segsize;
    assert(i < settings.segmaxnum);
    return seg_headers[i];
}
*/

static inline struct segment_header *segment_from_part(uint64_t addr) {
    int i;
    for(i=0;i<seg_alloced;i++) {
        struct segment_header *h = seg_headers[i];
        if(addr >= h->addr && addr < h->addr + h->size)
            return h;
    }
    printf("Cannot find segment at addr %p." % (void*) addr);
    abort();
    return NULL;
}

static void segment_free(struct segment_header *h)
{
  //printf("Free segment!\n");
    rte_spinlock_lock(&segalloc_lock);
    h->offset = 0;
    h->next = free_segments;
    free_segments = h;
    rte_spinlock_unlock(&segalloc_lock);
}

void segment_item_free(struct segment_header *h, size_t total)
{
  //printf("free: h->data = %p, size = %ld\n", h->data, total);
    if (h->size != __sync_add_and_fetch(&h->freed, total)) {
        assert(h->freed <= h->size);
        return;
    }
}

item *segment_item_alloc(uint64_t thisbase, uint64_t seglen, uint64_t* offset, size_t total)
{
    //printf("segment_header = %ld\n", h);
    item *it = (item *) (thisbase + *offset);
    //printf("item: seg_base = %p, thisbase = %ld, offset = %ld, total = %ld\n", seg_base, thisbase, *offset, total);
    size_t avail;

    /* Not enough room in this segment */
    avail = seglen - *offset;
    //printf("avail = %ld\n", avail);
    if (avail == 0) {
        return NULL;
    } else if (avail < total) {
    // TODO: may need this?
//        if (avail >= sizeof(item)) {
//            it->refcount = 0;
//            /* needed for log scan */
//            it->keylen = avail - sizeof(item);
//            it->vallen = 0;
//        }
        // The following should be done on APP.
        //segment_item_free(h, avail);
        //h->offset += avail;
        return NULL;
    }

    /* Ordering here is important */
    // TODO: may need this?
    //it->refcount = 1;

    *offset += total;

    return it;
}


//struct segment_header *new_segment(struct item_allocator *ia, bool cleanup) {
//  // TODO: ia
//    struct segment_header *h, *old;
//
//    __sync_synchronize();
//    if ((h = segment_alloc(ia->core_id)) == NULL) {
//        /* We're currently doing cleanup, and still have the reserved segment
//         * then that can be used now */
//        if (cleanup && ia->reserved != NULL) {
//            h = ia->reserved;
//            ia->reserved = NULL;
//        } else {
//            printf("Fail 2!\n");
//            return NULL;
//        }
//    }
//    h->next = NULL;
//    old = ia->cur;
//    old->next = h;
//    /* Mark old segment as GC-able */
//    old->flags |= SF_INACTIVE;
//    ia->cur = h;
//    __sync_synchronize();
//
////    printf("New segment %ld %ld %ld\n", old->next, old, ia->oldest);
////    printf("New segment %ld %d\n", ia->oldest->next, (ia->oldest->flags & SF_INACTIVE) == SF_INACTIVE);
//
//    return h;
//}


// TODO: use this instead
struct segment_header *ialloc_nicsegment_alloc(struct item_allocator *ia)
{
    struct segment_header *h;
    if (ia->reserved == NULL) {
        if ((ia->reserved = segment_alloc(ia->core_id)) == NULL) {
            return false;
        }
    }

    if ((h = segment_alloc(ia->core_id)) == NULL) {
        return false;
    }

    h->flags |= SF_NIC;
    h->next = NULL;
    if (ia->cur_nic == NULL) {
        ia->oldest_nic = h;
    } else {
        ia->cur_nic->next = h;
    }
    ia->cur_nic = h;

    return h;
}



item *segment_item_alloc_pointer(struct segment_header *h, size_t total)
{
    //printf("segment_header = %ld\n", h);
    item *it = (item *) ((uintptr_t) h->data + h->offset);
    size_t avail;

    /* Not enough room in this segment */
    avail = h->size - h->offset;
    //printf("avail = %ld\n", avail);
    if (avail == 0) {
        return NULL;
    } else if (avail < total) {
        if (avail >= sizeof(item)) {
            it->refcount = 0;
            /* needed for log scan */
            it->keylen = avail - sizeof(item);
            it->vallen = 0;
            it->addr = h->addr + h->offset;
        }
        // The following should be done on APP.
        segment_item_free(h, avail);
        h->offset += avail;
        return NULL;
    }

    /* Ordering here is important */
    it->addr = h->addr + h->offset;
    it->refcount = 1;
    h->offset += total;

    return it;
}

/** Mark NIC log segment as full. */
uint32_t ialloc_nicsegment_full(uintptr_t last)
{
  //printf("ialloc_nicsegment_full\n");
    struct segment_header *h = segment_from_part(last);
    size_t off = last - h->addr;
    printf("nicsegment_full: core_id =%d, h = %p, segment = %p, offset = %ld\n", h->core_id, h, h->data, off);

    /* If segment is not quite full yet, add dummy entry to fill up. */
    if (off + sizeof(item) <= h->size) {
        item *it = (item *) ((uintptr_t) h->data + off);
        it->refcount = 0;
        it->keylen = h->size - off - sizeof(item);
        it->vallen = 0;
    }
    segment_item_free(h, h->size - off);

    h->flags |= SF_INACTIVE;
    return h->core_id; 
}


void ialloc_init_allocator(struct item_allocator *ia, uint32_t core_id)
{
  printf("init allocator %p (%d)\n", ia, ia->core_id);
    struct segment_header *h;
    memset(ia, 0, sizeof(*ia));
    ia->core_id = core_id;

    if ((h = segment_alloc(ia->core_id)) == NULL) {
      printf("Allocating segment failed (1)\n");
        fprintf(stderr, "Allocating segment failed\n");
        abort();
    }

    h->next = NULL;
    ia->cur = h;
    ia->cur_nic = NULL;
    ia->oldest = h;
    ia->oldest_nic = NULL;
    ia->cleanup_queue = calloc(settings.segcqsize, sizeof(*ia->cleanup_queue));
    ia->cq_head = ia->cq_tail = 0;
    ia->cleaning = NULL;
    __sync_synchronize();
}

item *ialloc_alloc(struct item_allocator *ia, size_t total, bool cleanup)
{
    struct segment_header *h, *old;
    item *it;
    if(total > settings.segsize)
    assert(total < settings.segsize);

    /* If the reserved segment is currently active, only allocations for cleanup
     * are allowed */
    __sync_synchronize();
    if (ia->reserved == NULL && !cleanup) {
        printf("Only cleanup!\n");
        return NULL;
    }

    old = ia->cur;
    if ((it = segment_item_alloc_pointer(old, total)) != NULL) {
        return it;
    }

    if ((h = segment_alloc(ia->core_id)) == NULL) {
        /* We're currently doing cleanup, and still have the reserved segment
         * then that can be used now */
        if (cleanup && ia->reserved != NULL) {
            h = ia->reserved;
            ia->reserved = NULL;
        } else {
            printf("Fail 2!\n");
            return NULL;
        }
    }
    old->next = h;
    h->next = NULL;
    /* Mark old segment as GC-able */
    old->flags |= SF_INACTIVE;
    ia->cur = h;
    __sync_synchronize();

    it = segment_item_alloc_pointer(h, total);
    if (it == NULL) {
        printf("Fail 3!\n");
        return NULL;
    }
    return it;
}

void ialloc_free(item *it, size_t total)
{
    struct segment_header *h = segment_from_part(it->addr);
    //printf("free: segment = %p, it = %p, size = %ld\n", h->data, it, total);
    segment_item_free(h, total);
}

item *ialloc_cleanup_item(struct item_allocator *ia, bool idle)
{
    size_t i;
    item *it;

    __sync_synchronize();
    if (!idle) {
        if (ia->cleanup_count >= 32) {
            return NULL;
        }
        ia->cleanup_count++;
    }

    i = ia->cq_head;
    it = ia->cleanup_queue[i];
    if (it != NULL) {
        ia->cleanup_queue[i] = NULL;
        ia->cq_head = (i + 1) % settings.segcqsize;
    }
    if (ia->reserved == NULL) {
        ia->reserved = segment_alloc(ia->core_id);
    }
    __sync_synchronize();
    return it;
}

void ialloc_cleanup_nextrequest(struct item_allocator *ia)
{
    ia->cleanup_count = 0;
    __sync_synchronize();
}

void ialloc_maintenance(struct item_allocator *ia)
{
    struct segment_header *h, *prev, *next, *cand;
    item *it,  **cq = ia->cleanup_queue;
    size_t off, size, idx, i;
    double cand_ratio, ratio;
    void *data;

    /* Check if we can now free some segments? While we're at it, we can also
     * look for a candidate to be cleaned */
    cand = NULL;
    cand_ratio = 0;
    for (i = 0; i < 2; i++) {
        h = (i == 0 ? ia->oldest : ia->oldest_nic);
        prev = NULL;
        /* We stop before the last segment in the list, and if we hit any
         * non-inactive segments. This prevents us from having to touch the cur
         * pointers. */
        while (h != NULL && h->next != NULL &&
                (h->flags & SF_INACTIVE) == SF_INACTIVE)
        {
            next = h->next;
            ratio = (double) h->freed / h->size;
            /* Done with this segment? */
            if (h->freed == h->size) {
                if (prev == NULL) {
                    if (i == 0) {
                        ia->oldest = h->next;
                    } else {
                        ia->oldest_nic = h->next;
                    }
                } else {
                    prev->next = h->next;
                }
                segment_free(h);
                h = prev;
            } else if ((h->flags & SF_CLEANED) != SF_CLEANED) {
                /* Otherwise we also look for the next cleanup candidate if
                 * necessary */
                ratio = (double) h->freed / h->size;
                if (ratio >= 0.8 && ratio > cand_ratio) {
                    cand_ratio = ratio;
                    cand = h;
                }
            }
            prev = h;
            h = next;
        }
    }

    /* Check if we're currently working on cleaning a segment */
    h = ia->cleaning;
    off = ia->clean_offset;
    size = (h == NULL ? 0 : h->size);
    if (h == NULL || off == size) {
        h = cand;
        ia->cleaning = h;
        off = ia->clean_offset = 0;
        if (h != NULL) {
            h->flags |= SF_CLEANED;
        }
    }

    /* No segments to clean, that's great! */
    if (h == NULL) {
        return;
    }

    /* Enqueue clean requests to worker untill we run out or the queue is filled
     * up */
    idx = ia->cq_tail;
    data = h->data;
    while (off < size && cq[idx] == NULL) {
        it = (item *) ((uintptr_t) data + off);
        if (size - off < sizeof(item)) {
            off = size;
            break;
        }
        if (item_tryref(it)) {
            cq[idx] = it;
            idx = (idx + 1) % settings.segcqsize;
        }
        off += item_totalsz(it);
    }
    ia->cq_tail = idx;
    ia->clean_offset = off;
}

size_t clean_log(struct item_allocator *ia, bool idle)
{
    item *it, *nit;
    size_t n, m;

    if (!idle) {
        /* We're starting processing for a new request */
        ialloc_cleanup_nextrequest(ia);
    }

    n = 0, m = 0;
    while ((it = ialloc_cleanup_item(ia, idle)) != NULL) {
        n++;
        if (it->refcount != 1) {
	  //if(sizeof(*nit) + it->keylen + it->vallen > settings.segsize)
	  //printf("size problem: it = %p, size = %ld + %ld + %ld\n", it, sizeof(*nit), it->keylen, it->vallen);
            if ((nit = ialloc_alloc(ia, sizeof(*nit) + it->keylen + it->vallen,
                    true)) == NULL)
            {
                fprintf(stderr, "Warning: ialloc_alloc failed during cleanup :-/\n");
                abort();
            }

            nit->hv = it->hv;
            nit->vallen = it->vallen;
            nit->keylen = it->keylen;
            rte_memcpy(item_key(nit), item_key(it), it->keylen + it->vallen);
            hasht_put(nit, it);
            item_unref(nit);
	    m++;
        }
        item_unref(it);
	//if(it->refcount != 0)
	//  printf("old it->refcount = %d\n", it->refcount);
	//assert(it->refcount == 0);
    }
    //if(m>0) printf("clean: move %d items\n", m);
    return n;
}

struct item_allocator iallocs[NUM_THREADS];
bool init_allocator = false;

struct item_allocator* get_item_allocators() {
    if(!init_allocator) {
        init_allocator = true;
        printf("Init item_allocator\n");
        for(int i=0; i<NUM_THREADS; i++) {
            ialloc_init_allocator(&iallocs[i], i);
        }
    }
    return iallocs;
}

