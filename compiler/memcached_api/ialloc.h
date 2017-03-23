#include <stdio.h>
#include <stdlib.h>
#include "iokvs.h"

static item *segment_item_alloc(segment_header *h, size_t total)
{
    item *it = (item *) ((uintptr_t) h->data + h->offset);
    size_t avail;

    /* Not enough room in this segment */
    avail = h->size - h->offset;
    if (avail == 0) {
        return NULL;
    } else if (avail < total) {
        if (avail >= sizeof(item)) {
            it->refcount = 0;
            /* needed for log scan */
            it->keylen = avail - sizeof(item);
            it->vallen = 0;
        }
        //segment_item_free(h, avail);
        h->offset += avail;
        return NULL;
    }

    /* Ordering here is important */
    it->refcount = 1;

    h->offset += total;

    return it;
}