/*
 * Count-min Sketch header
 */
#ifndef _COUNT_MIN_SKETCH
#define _COUNT_MIN_SKETCH
#include <stdint.h>

#define CM_ROW_NUM 4
#define CM_COL_NUM 64 * 1024

void cm_sketch_init();
uint64_t cm_sketch_read(int row, uint32_t flow_id);
void cm_sketch_update(int row, uint32_t flow_id, uint64_t new_val);

#endif /* _COUNT_MIN_SKETCH */
