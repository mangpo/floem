#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
#include <stdint.h>
#include <inttypes.h>

#include "storm.h"
#include "hash.h"
#include "collections/hash_table.h"

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
#ifdef DEBUG_PERF
  static __thread size_t numexecutes = 0;
  static __thread uint64_t execute_time1 = 0;
  static __thread uint64_t execute_time2 = 0;
  uint64_t t1 = rdtsc();
#endif

  struct bucket *b = data;
  long sum = 0;
  struct tuple t;

  for(int i = 0; i < NUM_WINDOW_CHUNKS; i++) {
    sum += b->slots[i];
  }

  memset(&t, 0, sizeof(struct tuple));
  strcpy(t.v[0].str, b->str);
  t.v[0].integer = sum;
#ifdef DEBUG_PERF
  uint64_t t2 = rdtsc();
#endif

  tuple_send(&t, myself);
#ifdef DEBUG_MP
  printf("Count: %s %d | key = %ld, b = %p!!!!!!!!!!!!!!!\n", t.v[0].str, t.v[0].integer, key, b);
#endif

#ifdef DEBUG_PERF
  uint64_t t3 = rdtsc();
  numexecutes++;
  execute_time1 += t2 - t1;
  execute_time2 += t3 - t2;

  if(numexecutes == 1000000) {
    printf(">>> sum time: %.2f\n", 1.0*execute_time1/numexecutes);
    printf(">>> emit time: %.2f\n", 1.0*execute_time2/numexecutes);
    execute_time1 = execute_time2 = numexecutes = 0;
  }
#endif

  return 1;
}
#endif

void count_execute(const struct tuple *t, struct executor *self)
{
  assert(self != NULL);
  struct count_state *st = self->state;
  static __thread uintptr_t headslot = 0, tailslot = 1;
  static __thread time_t lasttime = 0;
#ifdef DEBUG_PERF
  static __thread time_t debug_lasttime = 0;
  static __thread size_t numexecutes = 0;
  static __thread uint64_t execute_time = 0;

 /* before_time = 0, hash_time = 0, lookup_time = 0, insert_time = 0; */

  uint64_t starttime = rdtsc(); // TODO: cavium

  numexecutes++;
#endif

  assert(t != NULL);

  if(myself == NULL) {
    myself = self;
  } else {
    assert(myself == self);
  }

  /* printf("Counter %d got '%s'.\n", t->task, t->v[0].str); */

  /* uint64_t before_hash = rdtsc(); */

  uint64_t key = hash(t->v[0].str, strlen(t->v[0].str), 0);

  /* uint64_t before_lookup = rdtsc(); */

  struct bucket *b = collections_hash_find(st->counts, key);

  /* uint64_t before_insert = rdtsc(); */

  if(b == NULL) {
    //printf(">>>>>>>>>>>>>> NEW BUCKET: %s key = %ld\n", t->v[0].str, key);
    b = malloc(sizeof(struct bucket));
    assert(b != NULL);
    memset(b, 0, sizeof(struct bucket));
    collections_hash_insert(st->counts, key, b);
    strcpy(b->str, t->v[0].str);
  }
  b->slots[headslot]++;

  /* usleep(10000); */

#ifdef DEBUG_PERF
  uint64_t now = rdtsc();
  /* before_time += before_hash - starttime; */
  /* hash_time += before_lookup - before_hash; */
  /* lookup_time += before_insert - before_lookup; */
  /* insert_time += now - before_insert; */
  execute_time += now - starttime;
  
  if(numexecutes == 1000000) {
    printf("count time: %.2f\n", 1.0*execute_time/numexecutes);
    execute_time = numexecutes = 0;
  }
#endif

  struct timeval tv;
  int r = gettimeofday(&tv, NULL);
  assert(r == 0);
  
  if(tv.tv_sec >= lasttime + DEFAULT_EMIT_FREQUENCY_IN_SECONDS) {
    lasttime = tv.tv_sec;
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
