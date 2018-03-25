#include "storm.h"
#include "worker.h"
#include "dpdk.h"
#include <unistd.h>

struct executor *executor;

void executor_thread(void *arg) {
  int tid = (long)arg;
  struct executor *self = &executor[tid];
  
  //printf("executor[%d] = %p, exe_id = %d\n", tid, self, self->exe_id);

  // Run dispatch loop
  for(;;) {
    if(!self->spout) {
      uint64_t gettime = rdtsc();
      q_buffer buff = inqueue_get(tid);
      struct tuple *t = (struct tuple *) buff.entry;
      assert(t != NULL);
      uint64_t starttime = rdtsc();
      self->execute(t, self);
      inqueue_advance(buff);  // old version: inqueue_advance(tid);
      uint64_t now = rdtsc();
      self->execute_time += now - starttime;
      self->get_time += starttime - gettime;
      self->numexecutes++;
      //}
    } else {
      uint64_t starttime = rdtsc();
      self->execute(NULL, self);
      uint64_t now = rdtsc();
      self->execute_time += now - starttime;
      self->numexecutes++;
    }
  }
}

void task_str(struct tuple *t, int task, const char* s) {
  if(t->task == task) {
    if(strcmp(t->v[0].str, s))
      printf("task = %d, str = %s\n", t->task, t->v[0].str);
    assert(strcmp(t->v[0].str, s) == 0);
  }
}

void tuple_send(struct tuple *t, struct executor *self)
{
  // Set source and destination
  t->fromtask = self->taskid;
  t->starttime = rdtsc();
  t->task = self->grouper(t, self);


  // Drop?
  if(t->task == 0) {
    return;
  }
  
#ifdef DEBUG
  task_str(t, 10, "golda");
  task_str(t, 11, "nathan");
  task_str(t, 12, "jackson");
  task_str(t, 13, "bertels");
#endif

  /* __sync_fetch_and_add(&target[t->task], 1); */

  // Put to outqueue
  //printf("tuple_send: task = %d, exe_id = %d\n", t->task, self->exe_id);
  outqueue_put(t, self->exe_id);

  self->emitted++;
}

int main(int argc, char *argv[]) {

    printf("tuple size = %d\n", sizeof(struct tuple));

    assert(argc > 1);
    int workerid = atoi(argv[1]);
    struct worker* workers = get_workers();
    executor = workers[workerid].executors;
    init_task2executor(executor);

    init(argv);
    printf("main: workerid = %d\n", workerid);

    pthread_t threads[MAX_EXECUTORS];
    for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
        printf("main: executor[%d] = %p\n", i, &executor[i]);
	executor[i].numexecutes = executor[i].lastnumexecutes = 0;
	executor[i].execute_time = executor[i].lastexecute_time = 0;
	executor[i].get_time = 0;
	executor[i].exe_id = i;
        if(executor[i].init != NULL) {
	  executor[i].init(&executor[i]);
         }
        int rc = pthread_create(&threads[i], NULL, executor_thread, (void *)i);
        if (rc){
            printf("ERROR; return code from pthread_create() is %d\n", rc);
            exit(-1);
        }
    }

    size_t lasttuples = 0, tuples;
    run_threads();
    int wait = 1;
    while(1) {
        dccp_print_stat();

#ifdef DEBUG_PERF
	for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
	  struct executor *e = &executor[i];
	  printf("%d: emitted %zu, get time %zu, execute time %zu, numexecutes %zu, avg. latency %zu\n",
		 e->taskid,
		 e->emitted,
		 e->get_time / (e->numexecutes > 0 ? e->numexecutes : 1),
		 e->execute_time / (e->numexecutes > 0 ? e->numexecutes : 1),
		 e->numexecutes,
		 e->avglatency / (e->numexecutes > 0 ? e->numexecutes : 1));
	}
#endif
    }
    kill_threads();

    return 0;
}
