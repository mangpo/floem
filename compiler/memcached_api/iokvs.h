#ifndef IOKVS_H_
#define IOKVS_H_

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
#include "protocol_binary.h"

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
    /** UDP port to listen on */
    uint16_t udpport;
    /** Verbosity for log messages. */
    uint8_t verbose;
};

/** Global settings */
struct settings settings;

/** Initialize global settings from command-line. */
void settings_init();

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
    struct segment_header *next;
    struct segment_header *prev;
    uint32_t offset;
    uint32_t freed;
    uint32_t size;
    uint32_t flags;
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
    /* Head pointer in cleanup queue */
    size_t cq_head;
    /* Clenanup counter, limits mandatory cleanup per request */
    size_t cleanup_count;

    uint8_t pad_1[40];
    /***********************************************************/
    /* Part 3: Only accessed by maintenance threads */

    /* Oldest segment */
    struct segment_header *oldest;
    /* Tail pointer for cleanup queue */
    size_t cq_tail;
    /*  */
    struct segment_header *cleaning;
    /*  */
    size_t clean_offset;
};


/** Initialize item allocation. Prepares memory regions etc. */
void ialloc_init(void);

/** Initialize an item allocator instance. */
void ialloc_init_allocator(struct item_allocator *ia);

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

item *segment_item_alloc(struct segment_header *h, size_t total);
struct segment_header *new_segment(struct item_allocator *ia, bool cleanup);
void segment_item_free(struct segment_header *h, size_t total);


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
    if ((c = __sync_sub_and_fetch(&it->refcount, 1)) == 0) {
        ialloc_free(it, item_totalsz(it));
    }
}

/** Wrapper for transport code */
static inline void myt_item_release(void *it)
{
    item_unref(it);
}

typedef struct {
    protocol_binary_request_header mcr;
    uint8_t payload[];
} __attribute__ ((packed)) iokvs_message;


uint32_t jenkins_hash(const void *key, size_t length);
void populate_hasht();

static item* random_item(size_t v) {
  size_t keylen = (v % 4) + 1;
  size_t vallen = (v % 4) + 1;

  item *it = (item *) malloc(sizeof(item) + keylen + vallen);
  it->keylen = keylen;
  it->vallen = vallen;
  uint8_t *key = item_key(it);
  uint8_t *val = item_value(it);
  for(size_t i=0; i<keylen; i++)
    key[i] = v;
  for(size_t i=0; i<vallen; i++)
    val[i] = v * 3;

  uint32_t hash = jenkins_hash(key, keylen);
  it->hv = hash;
  it->refcount = 1;
  return it;
}

static iokvs_message* random_get_request(size_t v, size_t id) {
  size_t keylen = (v % 4) + 1;
  size_t extlen = 4;

  iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + extlen + keylen);
  m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
  m->mcr.request.magic = id; // PROTOCOL_BINARY_REQ
  m->mcr.request.keylen = keylen;
  m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
  m->mcr.request.status = 0;

  m->mcr.request.extlen = extlen;
  m->mcr.request.bodylen = extlen + keylen;
  *((uint32_t *)m->payload) = 0;

  uint8_t* key = m->payload + extlen;
  for(size_t i=0; i<keylen; i++)
    key[i] = v;

  return m;
}

static iokvs_message* random_set_request(size_t v, size_t id) {
  size_t keylen = (v % 4) + 1;
  size_t vallen = (v % 4) + 1;
  size_t extlen = 4;

  iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + extlen + keylen + vallen);
  m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
  m->mcr.request.magic = id; // PROTOCOL_BINARY_REQ
  m->mcr.request.keylen = keylen;
  m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
  m->mcr.request.status = 0;

  m->mcr.request.extlen = extlen;
  m->mcr.request.bodylen = extlen + keylen + vallen;
  *((uint32_t *)m->payload) = 0;

  uint8_t* key = m->payload + extlen;
  for(size_t i=0; i<keylen; i++)
    key[i] = v;

  uint8_t* val = m->payload + extlen + keylen;
  for(size_t i=0; i<vallen; i++)
    val[i] = v * 3;

  return m;
}

static iokvs_message* random_request(size_t v) {
    if(v % 2 == 0)
        return random_set_request(v/2, v);
    else
        return random_get_request(v/2, v);
}

#endif // ndef IOKVS_H_
