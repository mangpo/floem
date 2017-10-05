#ifndef WORKER_H
#define WORKER_H

#include <assert.h>
#include <string.h>
#include "hash.h"
#include "storm.h"

#define ETHARP_HWADDR_LEN     6

struct eth_addr {
  uint8_t addr[ETHARP_HWADDR_LEN];
} __attribute__ ((packed));

struct ip_addr {
  uint8_t addr[4];
} __attribute__ ((packed));

struct worker {
  const char		*hostname;
  struct eth_addr	mac;
  struct ip_addr	ip;
  uint32_t		seq;
  uint16_t		port;
  int			sock;
  struct executor 	executors[MAX_EXECUTORS];
};

// All bolts
void print_execute(const struct tuple *t, struct executor *self);
void rank_execute(const struct tuple *t, struct executor *self);
void count_execute(const struct tuple *t, struct executor *self);
void spout_execute(const struct tuple *t, struct executor *self);

void spout_init(struct executor *self);
void count_init(struct executor *self);

struct worker* get_workers();
int fields_grouping(const struct tuple *t, struct executor *self);
int global_grouping(const struct tuple *t, struct executor *self);

void init_task2executor(struct executor *executor);
int *get_task2executorid();
int *get_task2worker();
struct executor *get_executors();
struct tuple* random_spout(size_t i);
struct tuple* random_count(size_t i);
struct tuple* random_rank(size_t i);

#if defined(BIGFISH) || defined(BIGFISH_FLEXNIC)
#	define PROC_FREQ	1600000.0	// bigfish (Khz)
#else
#	define PROC_FREQ	2200000.0	// swingout (Khz)
#endif

#define PROC_FREQ_MHZ	(uint64_t)(PROC_FREQ / 1000)

#define BATCH_SIZE	64			// in tuples
#define BATCH_DELAY	2000		// in us = (2000 * PROC_FREQ_MHZ) in cycles
#define LINK_RTT	(130)		// in us

#endif
