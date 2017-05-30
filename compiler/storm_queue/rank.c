#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
#include <stdint.h>

#include "storm.h"

#define DEFAULT_EMIT_FREQUENCY_IN_SECONDS	1
#define TOP_N					5

static int rank(const void *a, const void *b)
{
  const struct tuple *t1 = a, *t2 = b;
  return t2->v[0].integer - t1->v[0].integer;
}

void rank_execute(const struct tuple *t, struct executor *self)
{
  static __thread time_t lasttime = 0;
  static __thread struct tuple rankings[TOP_N + 1];

  /* printf("Ranker %d got '%s', %d.\n", t->task, t->v[0].str, t->v[0].integer); */

  for(int j = 0; j < MAX_VECTOR; j++) {
    if(t->v[j].integer == 0) {
      break;
    }

    // Update if already in ranking
    bool found = false;
    for(int i = 0; i <= TOP_N; i++) {
      if(!strcmp(rankings[i].v[0].str, t->v[j].str)) {
	rankings[i].v[0].integer = t->v[j].integer;
	found = true;
	break;
      }
    }

    // Append to end if not in ranking
    if(!found) {
      strcpy(rankings[TOP_N].v[0].str, t->v[j].str);
      rankings[TOP_N].v[0].integer = t->v[j].integer;
    }

    // Re-sort ranking
    qsort(rankings, TOP_N + 1, sizeof(struct tuple), rank);
  }

  struct timeval tv;
  int r = gettimeofday(&tv, NULL);
  assert(r == 0);

  if(tv.tv_sec >= lasttime + DEFAULT_EMIT_FREQUENCY_IN_SECONDS) {
    lasttime = tv.tv_sec;

    // Emit rankings
    struct tuple out;
    for(int i = 0; i < TOP_N; i++) {
      strcpy(out.v[i].str, rankings[i].v[0].str);
      out.v[i].integer = rankings[i].v[0].integer;
      /* printf("Rank %d, '%s', count %d\n", i, rankings[i].v[0].str, */
      /* 	     rankings[i].v[0].integer); */
    }

    tuple_send(&out, self);
  }
}
