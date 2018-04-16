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
#include "cvmx.h"
#include "cvmx-malloc.h"
#include "cvmx-bootmem.h"
#include <errno.h>
#include "cvmcs-nic-fwdump.h"
#include "cvmcs-nic-component.h"
#include "cvmcs-nic-hybrid.h"
#include "cvmcs-dcb.h"
#include "generated/cvmcs-nic-version.h"
#include "floem-util.h"

#include "storm.h"
#include "hash.h"
#include "hash_table.h"
#include "CAVIUM.h"

#define NUM_WINDOW_CHUNKS			5
#define DEFAULT_SLIDING_WINDOW_IN_SECONDS	(NUM_WINDOW_CHUNKS * 10) // 60
#define DEFAULT_EMIT_FREQUENCY_IN_SECONDS	(DEFAULT_SLIDING_WINDOW_IN_SECONDS / NUM_WINDOW_CHUNKS)

#define BUCKETS		5500000
/* #define BUCKETS		NUM_BUCKETS */

struct bucket {
  char	str[MAX_STR];
  long	slots[NUM_WINDOW_CHUNKS];
};

struct count_state {
  collections_hash_table *counts;
};

static __thread struct executor *myself = NULL;

static void tuple_free(void *t)
{
  assert(!"NYI");
}

void tuple_send(struct tuple *t, struct executor *self)
{
  // Set source and destination
  t->fromtask = nic_htonl(self->taskid);
  //t->starttime = rdtsc();
  t->task = nic_htonl(self->grouper(t, self));

  // Drop?
  if(t->task == 0) {
    return;
  }

  // Put to outqueue
  //printf("tuple_send: task = %d, exe_id = %d\n", t->task, self->exe_id);
  count_out(t, self->exe_id);

  self->emitted++;
}

#if 1
static int count_reset(uint64_t key, void *data, void *arg)
{
  uintptr_t slot = (uintptr_t)arg;
  struct bucket *b = data;

  b->slots[slot] = 0;

  return 1;
}

static int count_emit(uint64_t key, void *data, void *arg)
{

  struct bucket *b = data;
  long sum = 0;
  struct tuple t;

  for(int i = 0; i < NUM_WINDOW_CHUNKS; i++) {
    sum += b->slots[i];
  }

  memset(&t, 0, sizeof(struct tuple));
  strcpy(t.v[0].str, b->str);
  t.v[0].integer = nic_htonl(sum);

  tuple_send(&t, myself);
#ifdef DEBUG_MP
  printf("Count: %s %d | key = %ld, b = %p!!!!!!!!!!!!!!!\n", t.v[0].str, t.v[0].integer, key, b);
#endif

  return 1;
}
#endif

void count_execute(const struct tuple *t, struct executor *self)
{
  assert(self != NULL);
  struct count_state *st = self->state;
  static __thread uintptr_t headslot = 0, tailslot = 1;
  static __thread uint64_t lasttime = 0;

  assert(t != NULL);

  if(myself == NULL) {
    myself = self;
  } else {
    assert(myself == self);
  }

  /* printf("Counter %d got '%s'.\n", t->task, t->v[0].str); */

  uint64_t key = hash(t->v[0].str, strlen(t->v[0].str), 0);
  struct bucket *b = collections_hash_find(st->counts, key);

  if(b == NULL) {
    //printf(">>>>>>>>>>>>>> NEW BUCKET: %s key = %ld\n", t->v[0].str, key);
    b = shared_mm_malloc(sizeof(struct bucket));
    assert(b != NULL);
    memset(b, 0, sizeof(struct bucket));
    collections_hash_insert(st->counts, key, b);
    strcpy(b->str, t->v[0].str);
  }
  b->slots[headslot]++;

  /* usleep(10000); */

  uint64_t now = core_time_now_us();
  
  if(now >= lasttime + 1000000*DEFAULT_EMIT_FREQUENCY_IN_SECONDS) {
    lasttime = now;
#ifdef DEBUG_MP
    printf("Emit count\n");
#endif

#if 1
    // Emit all counts
    r = collections_hash_visit(st->counts, count_emit, NULL);
    assert(r != 0);

    // Wipe current window
    r = collections_hash_visit(st->counts, count_reset, (void *)tailslot);
    assert(r != 0);
#endif

    // Advance window
    headslot = tailslot;
    tailslot = (tailslot + 1) % NUM_WINDOW_CHUNKS;
  }

}

void count_init(struct executor *self)
{
  assert(self != NULL);
  self->state = malloc(sizeof(struct count_state));
  assert(self->state != NULL);
  struct count_state *st = self->state;
  printf("%d: Creating hash, self = %p\n", self->taskid, self);
  collections_hash_create_with_buckets(&st->counts, BUCKETS, tuple_free);
  assert(st->counts != NULL);
  printf("%d: hash created\n", self->taskid);
}
