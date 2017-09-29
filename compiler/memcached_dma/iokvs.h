#ifndef IOKVS_H_
#define IOKVS_H_


#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
#include "protocol_binary.h"

#define NUM_THREADS     6
//#define DEBUG

/******************************************************************************/
/* Settings */

/** Configurable settings */
struct settings {
    /** Size of log segments in bytes */
    size_t segsize;
    /** Maximal number of segments to use  */
    size_t segmaxnum;
    /** Size of seqment clean queue */
    size_t segcqsize;
    /** Local IP */
    struct ip_addr localip;
    /** Local IP */
    struct eth_addr localmac;
    /** UDP port to listen on */
    uint16_t udpport;
    /** Verbosity for log messages. */
    uint8_t verbose;
};

/** Global settings */
extern struct settings settings;
void settings_init(char *argv[]);

/**
 * Item.
 * The item struct is immediately followed by first the key, and then the
 * associated value.
 */
typedef struct _item {
    /** Next item in the hash chain. */
    struct _item *next;
    /** Hash value for this item */
    uint32_t hv;
    /** Length of value in bytes */
    uint32_t vallen;
    /** Reference count */
    /*volatile*/ uint16_t refcount;
    /** Length of key in bytes */
    uint16_t keylen;
    /** Flags (currently unused, but provides padding) */
    uint32_t flags;
    uint64_t addr;
} item;

/******************************************************************************/
/* Hash table operations */

/** Initialize hash table. */
void hasht_init(void);

/** Prefetch hash table slot */
void hasht_prefetch1(uint32_t hv);

/** Prefetch matching items */
void hasht_prefetch2(uint32_t hv);

/**
 * Lookup key in hash table.
 * @param key  Key
 * @param klen Length of key in bytes
 * @param hv   Hash of key
 * @return Pointer to item or NULL
 */
item *hasht_get(const void *key, size_t klen, uint32_t hv);

/**
 * Insert item into hash table
 * @param it  Item
 * @param cas If != NULL, will only store `it' if cas is the object currently
 *            stored for the key (compare and set).
 */
void hasht_put(item *it, item *cas);

struct segment_header {
    void *data;
    uint64_t addr;
    struct segment_header *next;
    struct segment_header *prev;
    uint32_t offset;
    uint32_t freed;
    uint32_t size;
    uint32_t flags;
    uint32_t core_id;
};


struct item_allocator {
    /***********************************************************/
    /* Part 1: mostly read-only for maintenance and worker */

    /* Reserved segment for log cleaning in case we run out */
    struct segment_header *reserved;
    /* Queue for communication  */
    item **cleanup_queue;

    uint8_t pad_0[48];
    /***********************************************************/
    /* Part 2: Only accessed by worker threads */

    /* Current segment */
    struct segment_header *cur;
    /* Current NIC segment */
    struct segment_header *cur_nic;
    /* Head pointer in cleanup queue */
    size_t cq_head;
    /* Clenanup counter, limits mandatory cleanup per request */
    size_t cleanup_count;

  uint16_t core_id;

  uint8_t pad_1[30]; // [32]
    /***********************************************************/
    /* Part 3: Only accessed by maintenance threads */

    /* Oldest segment */
    struct segment_header *oldest;
    /* Oldest NIC segment */
    struct segment_header *oldest_nic;
    /* Tail pointer for cleanup queue */
    size_t cq_tail;
    /*  */
    struct segment_header *cleaning;
    /*  */
    size_t clean_offset;
};


/** Initialize item allocation. Prepares memory regions etc. */
struct item_allocator* get_item_allocators();
void ialloc_init();

/** Initialize an item allocator instance. */
void ialloc_init_allocator(struct item_allocator *ia, uint32_t core_id);
size_t clean_log(struct item_allocator *ia, bool idle);

/**
 * Allocate an item.
 *
 * Note this function has two modes: cleanup and non-cleanup. In cleanup mode,
 * the allocator will use the segment reserved for log cleanup if no other
 * allocation is possible, otherwise it will just return NULL and leave the
 * reserved segment untouched.
 *
 * @param ia      Allocator instance
 * @param total   Total number of bytes (includes item struct)
 * @param cleanup true if this allocation is for a cleanup operation
 * @return Allocated item or NULL.
 */
item *ialloc_alloc(struct item_allocator *ia, size_t total,
        bool cleanup);

/**
 * Free an item.
 * @param it    Item
 * @param total Total number of bytes (includes item struct)
 */
void ialloc_free(item *it, size_t total);

/**
 * Get item from cleanup queue for this allocator.
 * @param ia   Allocator instance
 * @param idle true if there are currently no pending requests, false otherwise
 * @return Item or NULL
 */
item *ialloc_cleanup_item(struct item_allocator *ia, bool idle);

/**
 * Resets per-request cleanup counters. Should be called when a new request is
 * ready to be processed before calling ialloc_cleanup_item.
 */
void ialloc_cleanup_nextrequest(struct item_allocator *ia);

/**
 * Dispatch log cleanup operations for this instance, if required. To be called
 * from maintenance thread.
 */
void ialloc_maintenance(struct item_allocator *ia);

uint64_t segment_item_alloc(uint64_t thisbase, uint64_t seglen, uint64_t* offset, size_t total);
struct segment_header *ialloc_nicsegment_alloc(struct item_allocator *ia);
void segment_item_free(struct segment_header *h, size_t total);
uint32_t ialloc_nicsegment_full(uintptr_t last);

/******************************************************************************/
/* Items */


/** Get pointer to the item's key */
static inline void *item_key(item *it)
{
    return it + 1; // TODO: what is this point to?
}

/** Get pointer to the item's value */
static inline void *item_value(item *it)
{
    return (void *) ((uintptr_t) (it + 1) + it->keylen); // TODO: what is this point to?
}

/** Total number of bytes for this item (includes item struct) */
static inline size_t item_totalsz(item *it)
{
    return sizeof(*it) + it->vallen + it->keylen;
}

/** Increment item's refcount (original refcount must not be 0). */
static inline void item_ref(item *it)
{
    uint16_t old;
    old = __sync_add_and_fetch(&it->refcount, 1);
    assert(old != 1);
}

/**
 * Increment item's refcount if it is not zero.
 * @return true if the refcount was increased, false otherwise.
 */
static inline bool item_tryref(item *it)
{
    uint16_t c;
    do {
        c = it->refcount;
        if (c == 0) {
            return false;
        }
    } while (!__sync_bool_compare_and_swap(&it->refcount, c, c + 1));
    return true;
}

/**
 * Decrement item's refcount, and free item if refcount = 0.
 * The original refcount must be > 0.
 */
static inline void item_unref(item *it)
{
    uint16_t c;
    assert(it->refcount > 0);
    //if(it->refcount > 30) printf("refcount = %d\n", it->refcount);
    if ((c = __sync_sub_and_fetch(&it->refcount, 1)) == 0) {
      //printf("ialloc_free!!!!!!!!!!!!!!!!!!\n");
      ialloc_free(it, item_totalsz(it));
    }
}

/** Wrapper for transport code */
static inline void myt_item_release(void *it)
{
    item_unref(it);
}

typedef struct {
    struct eth_hdr ether;
    struct ip_hdr ipv4;
    struct udp_hdr udp;
    memcached_udp_header mcudp;
    protocol_binary_request_header mcr;
    uint8_t payload[];
} __attribute__ ((packed)) iokvs_message;

iokvs_message* iokvs_template();

uint32_t jenkins_hash(const void *key, size_t length);
//void populate_hasht();

iokvs_message* random_get_request(uint8_t v, uint8_t id);
iokvs_message* random_set_request(uint8_t v, uint8_t id);
iokvs_message* random_request(uint8_t v);
iokvs_message* double_set_request(uint8_t v);

#endif // ndef IOKVS_H_
