#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
#include <stdbool.h>

#include "storm.h"

//#define TWITTER_FEED

// in seconds
#ifndef LOCAL
#	define WAIT_TIME	2
#else
#	define WAIT_TIME	1
#endif

#ifndef TWITTER_FEED
/* static char *words[] = {"nathan", "mike", "jackson", "golda", "bertels"}; */
static char *words[] = {"nathan", "jackson", "golda", "bertels"};
static size_t numwords = sizeof(words) / sizeof(words[0]);
#endif

struct spout_state {
  char		**words;
  size_t	numwords;
};

void spout_execute(const struct tuple *t, struct executor *self)
{
  struct spout_state *st = self->state;
  struct tuple myt;
  static __thread bool send = false;
#ifndef TWITTER_FEED
  static __thread bool init = false;
  static __thread struct random_data mybuf;
  static __thread char statebuf[256];
  int r, i;
#else
  static __thread int i = 0;
#endif

  struct timeval start;
  r = gettimeofday(&start, NULL);

  static __thread size_t count = 0, sum = 0;
  size_t starttime = rdtsc();

#ifndef TWITTER_FEED
  if(!init) {
    r = initstate_r(self->taskid, statebuf, 256, &mybuf);
    assert(r == 0);
    init = true;
  }

  r = random_r(&mybuf, &i);
  assert(r == 0);
  i %= st->numwords;
#endif

  assert(t == NULL);

  if(!send) {
    usleep(WAIT_TIME * 1000000);
    send = true;
  }

#ifdef DEBUG_MP
    sleep(1);
#else
    //usleep(1);
#endif

  memset(&myt, 0, sizeof(struct tuple));
  strcpy(myt.v[0].str, st->words[i]);
#ifdef DEBUG_MP
  printf("%d: Spout emitting '%s'.\n", self->taskid, st->words[i]);
#endif
  size_t endtime = rdtsc();
  count++;
  sum += endtime - starttime;
  if(count == 1000000) {
    printf("spout time: %.2f\n", 1.0*sum/count);
    count = sum = 0;
  }

  tuple_send(&myt, self);

#ifdef TWITTER_FEED
  i = (i + 1) % st->numwords;
  /* if(i == 0) { */
  /*   printf("%d: Wrapped around!\n", self->taskid); */
  /* } */
#endif

  /* struct timeval now; */
  /* r = gettimeofday(&now, NULL); */
  /* static __thread long int total_time = 0; */
  /* static __thread size_t total_count = 0; */

  /* total_time += (now.tv_sec*1000000 + now.tv_usec) - (start.tv_sec*1000000 + start.tv_usec); */
  /* total_count++; */
  
  /* if(total_count == 100000) { */
  /*   printf("Spout latency %ld\n", total_time/total_count); */
  /*   total_time = 0; */
  /*   total_count = 0; */
  /* } */
  
}

void spout_init(struct executor *self)
{
  assert(self != NULL);
  self->state = malloc(sizeof(struct spout_state));
  assert(self->state != NULL);
  struct spout_state *st = self->state;

#ifndef TWITTER_FEED
  st->words = words;
  st->numwords = numwords;
#else
    // Load twitter feed
    char filename[256];
    snprintf(filename, 256, "unames-%d.txt", self->taskid);
    FILE *f = fopen(filename, "r");
    assert(f != NULL);

    int r = fscanf(f, "%zu\n", &st->numwords);
    assert(r == 1);

    printf("Reading %zu names\n", st->numwords);

    st->words = malloc(st->numwords * sizeof(char *));
    assert(st->words != NULL);

    /* int lastpct = 0; */
    for(size_t i = 0; i < st->numwords; i++) {
      /* int newpct = (i * 100) / st->numwords; */
      /* if(newpct > lastpct + 25) { */
      /* 	printf("%d: Done %u %%\n", self->taskid, newpct); */
      /* 	lastpct = newpct; */
      /* } */

      st->words[i] = malloc(MAX_STR);
      assert(st->words[i] != NULL);
      char *ret = fgets(st->words[i], MAX_STR, f);
      assert(ret != NULL);
      assert(st->words[i][strlen(st->words[i]) - 1] == '\n');
      st->words[i][strlen(st->words[i]) - 1] = '\0';
    }

    fclose(f);

    printf("%d: Done reading.\n", self->taskid);
#endif
}
