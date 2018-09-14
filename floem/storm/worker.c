#include "worker.h"
#include "dccp.h"
#include <stdio.h>

struct tuple* random_spout(size_t i) {
  return NULL;
}

struct tuple* random_count(size_t i) {
  struct tuple* t = (struct tuple*) malloc(sizeof(struct tuple));
  t->task = 10;
  if(i%4==0) {
    strcpy(t->v[0].str, "mangpo");
  }
  else if(i%4==1) {
    strcpy(t->v[0].str, "maprang");
  }
  else if(i%4==2) {
    strcpy(t->v[0].str, "hua");
  }
  else {
    strcpy(t->v[0].str, "pom");
  }
  return t;
}

struct tuple* random_rank(size_t i) {
  struct tuple* t = (struct tuple*) malloc(sizeof(struct tuple));
  t->task = 20;
  if(i%4==0) {
    t->v[0].integer = 1;
    strcpy(t->v[0].str, "mangpo");
  }
  else if(i%4==1) {
    t->v[0].integer = 2;
    strcpy(t->v[0].str, "maprang");
  }
  else if(i%4==2) {
    t->v[0].integer = 3;
    strcpy(t->v[0].str, "hua");
  }
  else {
    t->v[0].integer = 4;
    strcpy(t->v[0].str, "pom");
  }
  return t;
}

void init_header_template(struct pkt_dccp_headers *p) {
  //memcpy(&p->eth.src, l2fwd_ports_eth_addr[0].addr_bytes, ETHARP_HWADDR_LEN);                         
  p->eth.type = htons(ETHTYPE_IP);

  // Initialize IP header                                                                               
  p->ip._v_hl = 69;
  p->ip._tos = 0;
  p->ip._id = htons(3);
  p->ip._offset = 0;
  p->ip._ttl = 0xff;
  p->ip._proto = IP_PROTO_DCCP;
  p->ip._chksum = 0;
  //p->ip.src.addr = 0; // arranet_myip
  p->ip._len = htons(sizeof(struct tuple) + sizeof(struct dccp_hdr) + IP_HLEN);

  p->dccp.data_offset = 3;
  p->dccp.res_type_x = DCCP_TYPE_DATA << 1;
  p->dccp.ccval_cscov = 1;
}

void init_congestion_control(struct connection* connections) {
  int i;
  for(i = 0; i < MAX_WORKERS; i++) {
    connections[i].cwnd = 4;
    connections[i].acks = 0;
    connections[i].lastack = 0;
  }
}

//__attribute__ ((unused))
int fields_grouping(const struct tuple *t, struct executor *self)
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

//__attribute__ ((unused))
int global_grouping(const struct tuple *t, struct executor *self)
{
  return self->outtasks[0];
}

#define SYSLAB_CAVIUM2

struct worker workers[MAX_WORKERS] = {
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
  
#elif defined(SYSLAB_DPDK)
  {
    .hostname = "dikdik", .ip.addr = "\x0a\x64\x14\x05", .port = 1234, .mac.addr = "\x3c\xfd\xfe\xad\x84\x8d",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },

      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },

      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "fossa", .ip.addr = "\x0a\x64\x14\x07", .port = 1234, .mac.addr = "\x3c\xfd\xfe\xad\xfe\x05",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },

      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },

      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(SYSLAB_DPDK2)
  {
    .hostname = "guanaco", .ip.addr = "\x0a\x64\x14\x08", .port = 1234, .mac.addr = "\x3c\xfd\xfe\xaa\xd1\xe1",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "hippopotamus", .ip.addr = "\x0a\x64\x14\x09", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x41",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },

#elif defined(SYSLAB_CAVIUM)
  {
    .hostname = "jaguar", .ip.addr = "\x0a\x64\x14\x0b", .port = 1234, .mac.addr = "\x02\x78\x1f\x5a\x5b\x01",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "quagga", .ip.addr = "\x0a\x64\x14\x12", .port = 1234, .mac.addr = "\x00\x0f\xb7\x30\x3f\x59",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },

#elif defined(SYSLAB_CAVIUM2)
  {
    .hostname = "jaguar", .ip.addr = "\x0a\x64\x14\x0b", .port = 1234, .mac.addr = "\x02\x78\x1f\x5a\x5b\x01",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11 }, .grouper = fields_grouping, .cpu = true },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping, .cpu = true },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21 }, .grouper = fields_grouping, .cpu = false },
    }
  },
  {
    .hostname = "quagga", .ip.addr = "\x0a\x64\x14\x12", .port = 1234, .mac.addr = "\x00\x0f\xb7\x30\x3f\x59",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11 }, .grouper = fields_grouping, .cpu = true },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping, .cpu = true },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping, .cpu = true },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21 }, .grouper = fields_grouping, .cpu = false },
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
    .hostname = "10.3.0.30", .ip.addr = "\x0a\x03\x00\x1e", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x40",	// sampa1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.33", .ip.addr = "\x0a\x03\x00\x21", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x11\x3c",	// sampa2
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
    }
  },
  
#elif defined(SAMPA_DPDK)
  {
    .hostname = "10.3.0.30", .ip.addr = "\x0a\x03\x00\x1e", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x40",	// sampa1
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.33", .ip.addr = "\x0a\x03\x00\x21", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x11\x3c",	// sampa2
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(SAMPA_DPDK2)
  {
    .hostname = "10.3.0.30", .ip.addr = "\x0a\x03\x00\x1e", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x40",       // sampa1                    
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.33", .ip.addr = "\x0a\x03\x00\x21", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x11\x3c",       // sampa2                    
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },

#elif defined(SAMPA_CAVIUM)
  {
    .hostname = "10.3.0.35", .ip.addr = "\x0a\x03\x00\x23", .port = 1234,  .mac.addr = "\x00\x0f\xb7\x30\x3f\x58",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.36", .ip.addr = "\x0a\x03\x00\x24", .port = 1234,  .mac.addr = "\x02\xaf\x01\x8b\xb5\x00",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 23, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },
#elif defined(SAMPA_CAVIUM2)
  {
    .hostname = "10.3.0.35", .ip.addr = "\x0a\x03\x00\x23", .port = 1234,  .mac.addr = "\x00\x0f\xb7\x30\x3f\x58",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.36", .ip.addr = "\x0a\x03\x00\x24", .port = 1234,  .mac.addr = "\x02\xaf\x01\x8b\xb5\x00",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 30, .outtasks = { 0 }, .grouper = global_grouping },
    }
  },

#elif defined(SAMPA_DPDK_CAVIUM)
  {
    .hostname = "10.3.0.35", .ip.addr = "\x0a\x03\x00\x23", .port = 1234,  .mac.addr = "\x00\x0f\xb7\x30\x3f\x58", // 00:0f:b7:30:3f:58
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 1, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 2, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 10, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 11, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 20, .outtasks = { 30 }, .grouper = global_grouping },
      { .execute = rank_execute, .taskid = 21, .outtasks = { 30 }, .grouper = global_grouping },
    }
  },
  {
    .hostname = "10.3.0.30", .ip.addr = "\x0a\x03\x00\x1e", .port = 1234, .mac.addr = "\x68\x05\xca\x33\x13\x40",
    .executors = {
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 3, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = spout_execute, .init = spout_init, .spout = true, .taskid = 4, .outtasks = { 10, 11, 12, 13 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 12, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = count_execute, .init = count_init, .taskid = 13, .outtasks = { 20, 21, 22, 23 }, .grouper = fields_grouping },
      { .execute = rank_execute, .taskid = 22, .outtasks = { 30 }, .grouper = global_grouping },
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

struct worker* get_workers() { 
  return workers; }


struct executor *task2executor[MAX_TASKS];
int task2executorid[MAX_TASKS];
int task2worker[MAX_TASKS];
struct executor *my_executors;

int *get_task2executorid() {
  return task2executorid;
}

int *get_task2worker() {
  return task2worker;
}

struct executor *get_executors() {
  printf("get: executors = %p\n", my_executors);
  return my_executors;
}

void init_task2executor(struct executor *executor) {
  my_executors = executor;
  int i, j;
  for(i = 0; i < MAX_TASKS; i++) {
    task2executorid[i] = -1;
    task2worker[i] = -1;
  }
  for(i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
    printf("init: executor[%d] = %p, taskid = %d\n", i, &executor[i], executor[i].taskid);
    assert(task2executor[executor[i].taskid] == NULL);
    task2executor[executor[i].taskid] = &executor[i];
    task2executorid[executor[i].taskid] = i;
  }
  for(i = 0; i < MAX_WORKERS && workers[i].hostname != NULL; i++) {
    for(j = 0; j < MAX_EXECUTORS && workers[i].executors[j].execute != NULL; j++) {
      task2worker[workers[i].executors[j].taskid] = i;
    }
  }
  printf("init: executors = %p\n", my_executors);
}
