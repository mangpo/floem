/*
 * Count-min Sketch implementation
 */

#include "count-min-sketch.h"
#include "pkt-utils.h"

#ifdef CAVIUM
#include "cvmx.h"
#include "cvmx-atomic.h"
#include "shared-mm.h"
#include "util.h"
#else
#include <dpdkif.h>
#endif

/*
 * Note that we support atomic read/write on the count-min sketch
 * table (cm_sketch). This requires all the table cell to be 64-bits
 * aligned. Therefore, we start at an aligned address and each cell
 * address is also an aligned address.
 */
#ifdef CAVIUM
CVMX_SHARED uint64_t *cm_sketch;

void
cm_sketch_init()
{
    cm_sketch = (uint64_t *)shared_mm_memalign(sizeof(uint64_t) *
                                               CM_ROW_NUM * CM_COL_NUM, 8);
    memset(cm_sketch, 0x00, sizeof(uint64_t) * CM_ROW_NUM * CM_COL_NUM);
}
#else
uint64_t *cm_sketch;

void
cm_sketch_init()
{
    cm_sketch = (uint64_t *) malloc(sizeof(uint64_t) *
                                               CM_ROW_NUM * CM_COL_NUM, 8);
    memset(cm_sketch, 0x00, sizeof(uint64_t) * CM_ROW_NUM * CM_COL_NUM);
#endif

/*
 * Experienced method online. The result is nearly good as AES.
 */
uint32_t
cm_hash1 (uint32_t x)
{
    x = ((x >> 16) ^ x) * 0x45d9f3b;
    x = ((x >> 16) ^ x) * 0x45d9f3b;
    x = (x >> 16) ^ x;
    return x;
}

/*
 * Robert Jenkin's hashing method
 */
uint32_t
cm_hash2 (uint32_t a)
{
    a = (a+0x7ed55d16) + (a<<12);
    a = (a^0xc761c23c) ^ (a>>19);
    a = (a+0x165667b1) + (a<<5);
    a = (a+0xd3a2646c) ^ (a<<9);
    a = (a+0xfd7046c5) + (a<<3);
    a = (a^0xb55a4f09) ^ (a>>16);
    return a;
}

/*
 * Thomas Wang's hashing method
 */
uint32_t
cm_hash3(uint32_t a)
{
    a = (a ^ 61) ^ (a >> 16);
    a = a + (a << 3);
    a = a ^ (a >> 4);
    a = a * 0x27d4eb2d;
    a = a ^ (a >> 15);
    return a;
}

/*
 * Knuth's multiplicative hashing method
 */
uint32_t
cm_hash4(uint32_t v)
{
    return v * UINT32_C(2654435761);
}

static uint32_t
flow_to_hash(int row,
             uint32_t flow_id)
{
    uint32_t ret;

    switch (row) {
        case 0: ret = cm_hash1(flow_id); break;
        case 1: ret = cm_hash2(flow_id); break;
        case 2: ret = cm_hash3(flow_id); break;
        case 3: ret = cm_hash4(flow_id); break;
        default: ret = flow_id; break;
    }

    return ret;
}

uint64_t
cm_sketch_read(int row,
               uint32_t flow_id)
{
    uint32_t bucket_id = flow_to_hash (row, flow_id) % CM_COL_NUM;
    uint64_t ret_val = cm_sketch[row * CM_ROW_NUM + bucket_id];

    return ret_val;
}

#define MAX(a,b) (((a)>(b))?(a):(b))

void
cm_sketch_update(int row,
                 uint32_t flow_id,
                 uint64_t new_val)
{
    uint32_t bucket_id = flow_to_hash (row, flow_id) % CM_COL_NUM;
    uint64_t *write_addr = cm_sketch + row * CM_ROW_NUM + bucket_id;
    uint64_t old_val = *write_addr;

    while (!__sync_bool_compare_and_swap64(write_addr, old_val, new_val)) {
        old_val = *write_addr;
        new_val = MAX(old_val, new_val);
    }
}
