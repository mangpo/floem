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
  //uint32_t addr;
  uint8_t addr[4];
} __attribute__ ((packed));


struct worker {
  const char		*hostname;
  struct eth_addr	mac;
  struct ip_addr        ip;
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

__attribute__ ((unused))
static int fields_grouping(const struct tuple *t, struct executor *self)
{
  static __thread int numtasks = 0;

  if(numtasks == 0) {
    // Remember number of tasks
    for(numtasks = 0; numtasks < MAX_TASKS; numtasks++) {
      if(self->outtasks[numtasks] == 0) {
	break;
      }
    }
    assert(numtasks > 0);
  }

  return self->outtasks[hash(t->v[0].str, strlen(t->v[0].str), 0) % numtasks];
}

__attribute__ ((unused))
static int global_grouping(const struct tuple *t, struct executor *self)
{
  return self->outtasks[0];
}

__attribute__ ((unused))
static int shuffle_grouping(const struct tuple *t, struct executor *self)
{
  static __thread int numtasks = 0;

  if(numtasks == 0) {
    // Remember number of tasks
    for(numtasks = 0; numtasks < MAX_TASKS; numtasks++) {
      if(self->outtasks[numtasks] == 0) {
	break;
      }
    }
    assert(numtasks > 0);
  }

  return self->outtasks[random() % numtasks];
}

#define SAMPA_DPDK_CAVIUM

static struct worker workers[MAX_WORKERS] = {
#if defined(LOCAL)
  {
    .hostname = "127.0.0.1", .port = 7001,
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
    }
  },
  {
    .hostname = "127.0.0.1", .port = 7002,
    .executors = {
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
    }
  },
  {
    .hostname = "127.0.0.1", .port = 7003,
    .executors = {
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "127.0.0.1", .port = 7004,
    .executors = {
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
      /* { .execute = print_execute, .taskid = 40 }, */
    }
  },
#elif defined(SWINGOUT_LOCAL)
  {
    .hostname = "127.0.0.1", .port = 7001,	// swingout1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "127.0.0.1", .port = 7002,	// swingout4
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "127.0.0.1", .port = 7003,	// swingout3
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(SAMPA_LOCAL)
  {
    .hostname = "127.0.0.1", .port = 7001,	// sampa1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "127.0.0.1", .port = 7002,	// sampa2
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(SAMPA_TEST)
  {
    .hostname = "10.3.0.30", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x41",	// sampa1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
    }
  },
  {
    .hostname = "10.3.0.33", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x11\x3d",	// sampa2
    .executors = {
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
    }
  },
#elif defined(SAMPA)
  {
    .hostname = "10.3.0.30", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x41",	// sampa1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.33", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x11\x3d",	// sampa2
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(SAMPA_DPDK_CAVIUM)
  {
    .hostname = "10.3.0.30", .ip.addr = "\x0a\x03\x00\x1e", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x41",	// sampa1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.35", .ip.addr = "\x0a\x03\x00\x23", .port = 1234, .mac.addr = "\x00\x0f\xb7\x30\x3f\x58",	// sampa2
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(BIGFISH)
  {
    .hostname = "128.208.6.106", .port = 7001,
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.106", .port = 7002,
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.106", .port = 7003,
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(BIGFISH_FLEXNIC)
  {
    /* .hostname = "128.208.6.106", .port = 7001, */
    .hostname = "192.168.26.22", .port = 7001,
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    /* .hostname = "128.208.6.106", .port = 7002, */
    .hostname = "192.168.26.22", .port = 7002,
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    /* .hostname = "128.208.6.106", .port = 7003, */
    .hostname = "192.168.26.22", .port = 7003,
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(BIGFISH_FLEXNIC_DPDK)
  {
    .hostname = "128.208.6.236", .port = 7001, .mac.addr = "\xa0\x36\x9f\x0f\xfb\xe0",	// swingout3
    /* .hostname = "192.168.26.8", .port = 7001, .mac.addr = "\xa0\x36\x9f\x0f\xfb\xe0",	// swingout3 */
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.106", .port = 7002, .mac.addr = "\xa0\x36\x9f\x10\x03\x20",	// bigfish
    /* .hostname = "192.168.26.22", .port = 7002, .mac.addr = "\xa0\x36\x9f\x10\x03\x20",	// bigfish */
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.130", .port = 7003, .mac.addr = "\xa0\x36\x9f\x10\x00\xa0",	// swingout5
    /* .hostname = "192.168.26.20", .port = 7003, .mac.addr = "\xa0\x36\x9f\x10\x00\xa0",	// swingout5 */
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(BIGFISH_FLEXNIC_DPDK2)
  {
    .hostname = "128.208.6.236", .port = 7001, .mac.addr = "\xa0\x36\x9f\x0f\xfb\xe0",	// swingout3
    /* .hostname = "192.168.26.8", .port = 7001, .mac.addr = "\xa0\x36\x9f\x0f\xfb\xe0",	// swingout3 */
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.106", .port = 7002, .mac.addr = "\xa0\x36\x9f\x10\x03\x20",	// bigfish
    /* .hostname = "192.168.26.22", .port = 7002, .mac.addr = "\xa0\x36\x9f\x10\x03\x20",	// bigfish */
    .executors = {
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
    }
  },
  {
    .hostname = "128.208.6.130", .port = 7003, .mac.addr = "\xa0\x36\x9f\x10\x00\xa0",	// swingout5
    /* .hostname = "192.168.26.20", .port = 7003, .mac.addr = "\xa0\x36\x9f\x10\x00\xa0",	// swingout5 */
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(SWINGOUT_BALANCED)
  {
    .hostname = "128.208.6.67", .port = 7001,	// swingout1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.129", .port = 7002,	// swingout4
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.236", .port = 7003,	// swingout3
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
  /* { */
  /*   .hostname = "128.208.6.236", .port = 7004,	// swingout3 */
  /*   .executors = { */
  /*     /\* { .execute = print_execute, .taskid = 40 }, *\/ */
  /*   } */
  /* }, */
#elif defined(SWINGOUT_GROUPED)
  {
    .hostname = "128.208.6.67", .port = 7001,	// swingout1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
    }
  },
  {
    .hostname = "128.208.6.106", .port = 7002,	// bigfish
    /* .hostname = "128.208.6.129", .port = 7002,	// swingout4 */
    .executors = {
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
    }
  },
  {
    .hostname = "128.208.6.236", .port = 7003,	// swingout3
    .executors = {
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "128.208.6.236", .port = 7004,	// swingout3
    .executors = {
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
      /* { .execute = print_execute, .taskid = 40 }, */
    }
  },
#else
#	error Need to define a topology!
#endif
  { .hostname = NULL }
};

void init_task2executor(struct executor *executor);
int *get_task2executorid();
int *get_task2worker();
struct executor *get_executors();
struct tuple* random_spout(size_t i);
struct tuple* random_count(size_t i);
struct tuple* random_rank(size_t i);

#if defined(BIGFISH) || defined(BIGFISH_FLEXNIC) || defined(SAMPA)
#	define PROC_FREQ	1600000.0	// bigfish (Khz)
#else
#	define PROC_FREQ	2200000.0	// swingout (Khz)
#endif

#define PROC_FREQ_MHZ	(uint64_t)(PROC_FREQ / 1000)

#define BATCH_SIZE	64			// in tuples
#define BATCH_DELAY	2000		// in us = (2000 * PROC_FREQ_MHZ) in cycles
#define LINK_RTT	(130)		// in us

#endif
