#include "storm.h"
#include "worker.h"
//#include "flexstorm.h"
#include "dpdk.h"

struct executor *executor;

void executor_thread(void *arg) {
  int tid = (long)arg;
  struct executor *self = &executor[tid];
  
  // Run dispatch loop
  for(;;) {
    if(!self->spout) {
      q_buffer buff = inqueue_get(tid);
      struct tuple *t = (struct tuple *) buff.entry;
      assert(t != NULL);
      //if(t != NULL) {
        uint64_t starttime = rdtsc();
        self->execute(t, self);
        //printf("Tuple %d done\n", t->task);
        uint64_t now = rdtsc();
        inqueue_advance(buff);  // old version: inqueue_advance(tid);
        self->execute_time += now - starttime;
        self->numexecutes++;
      //}
    } else {
      //printf("spout\n");
      uint64_t starttime = rdtsc();
      self->execute(NULL, self);
      uint64_t now = rdtsc();
      self->execute_time += now - starttime;
      self->numexecutes++;
    }
  }
}

void tuple_send(struct tuple *t, struct executor *self)
{
  // Set source and destination
  t->fromtask = self->taskid;
  t->task = self->grouper(t, self);
  t->starttime = rdtsc();


  // Drop?
  if(t->task == 0) {
    return;
  }

  /* __sync_fetch_and_add(&target[t->task], 1); */

  // Put to outqueue
  //printf("tuple_send: task = %d, exe_id = %d\n", t->task, self->exe_id);
  outqueue_put(t, self->exe_id);

  self->emitted++;
}

int main(int argc, char *argv[]) {
    assert(argc > 1);
    int workerid = atoi(argv[1]);
    executor = workers[workerid].executors;
    init_task2executor(executor);

    init(argv);
    printf("main: workerid = %d\n", workerid);

    pthread_t threads[MAX_EXECUTORS];
    for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
        printf("main: executor[%d] = %p\n", i, &executor[i]);
        if(executor[i].init != NULL) {
            executor[i].exe_id = i;
            executor[i].init(&executor[i]);
         }
        int rc = pthread_create(&threads[i], NULL, executor_thread, (void *)i);
        if (rc){
            printf("ERROR; return code from pthread_create() is %d\n", rc);
            exit(-1);
        }
    }

    DccpInfo* info = get_dccp_stat();

    size_t sum = 0, lasttuples = 0, tuples;
    run_threads();
    while(1) {
        sleep(1);
        sum = 0;
        __sync_synchronize();
	struct connection* connections = info->connections;
        /* for(int i = 0; i < MAX_WORKERS; i++) { */
        /*     printf("pipe,cwnd,acks,lastack[%d] = %u, %u, %zu, %d\n", i, */
        /*     connections[i].pipe, connections[i].cwnd, connections[i].acks, connections[i].lastack); */
        /* } */
        tuples = info->tuples - lasttuples;
        lasttuples = info->tuples;
        printf("acks sent %zu, rtt %" PRIu64 "\n", info->acks_sent, info->link_rtt);
        printf("Tuples/s: %zu, Gbits/s: %.2f\n\n",
           tuples, (tuples * sizeof(struct tuple) * 8) / 1000000000.0);
    }
    kill_threads();

    return 0;
}
