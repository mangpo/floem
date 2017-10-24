#include "storm.h"
#include "worker.h"
#include "app.h"

struct executor *executor;

void executor_thread(void *arg) {
  int tid = (long)arg;
  struct executor *self = &executor[tid];
  
  // Run dispatch loop
  q_buffer buff;
  bool from_bypass;
  for(;;) {
    if(!self->spout) {
        q_buffer buff;
	// TODO: order?
        //if(!buff.entry) {
            buff = inqueue_get(tid);
            from_bypass = false;
	    //}
        if(!buff.entry) {
            buff = bypass_get(tid);
            from_bypass = true;
        }
        if(!buff.entry) continue;

        struct tuple *t = (struct tuple *) buff.entry;
#ifdef DEBUG_MP
	printf("\ngot: task %d = %d, bypass %d\n", t->task, t->task & 0xffffff, from_bypass);
#endif

#ifdef CHECK
        assert(t != NULL);
	if((t->task & 0xffffff) == 10 && strcmp(t->v[0].str, "golda"))
	  printf(">>> task = %d, str = %s, bypass = %d\n", t->task & 0xffffff, t->v[0].str, from_bypass);
	if((t->task & 0xffffff) == 11 && strcmp(t->v[0].str, "nathan"))
	  printf(">>> task = %d, str = %s, bypass = %d\n", t->task & 0xffffff, t->v[0].str, from_bypass);
	if((t->task & 0xffffff) == 12 && strcmp(t->v[0].str, "jackson"))
	  printf(">>> task = %d, str = %s, bypass = %d\n", t->task & 0xffffff, t->v[0].str, from_bypass);
	if((t->task & 0xffffff) == 13 && strcmp(t->v[0].str, "bertels"))
	  printf(">>> task = %d, str = %s, bypass = %d\n", t->task & 0xffffff, t->v[0].str, from_bypass);

	//	if((t->task & 0xffffff) == 12 || (t->task & 0xffffff) == 13)
	//printf("task = %d, str = %s\n", t->task & 0xffffff, t->v[0].str);
#endif

        char* s = t->v[0].str;
#ifdef CHECK
	if(!(strcmp(s, "nathan")==0 || strcmp(s, "golda")==0 || strcmp(s, "bertels")==0 || strcmp(s, "jackson")==0))
	  printf("BAD: %s, len = %d\n", s, strlen(s)); 
        assert(strcmp(s, "nathan")==0 || strcmp(s, "golda")==0 || strcmp(s, "bertels")==0 || strcmp(s, "jackson")==0);
#endif
      //if(t != NULL) {
        uint64_t starttime = rdtsc();
        self->execute(t, self);
        //printf("Tuple %d done\n", t->task);

        if(from_bypass)
            bypass_advance(buff);
        else
            inqueue_advance(buff);

        uint64_t now = rdtsc();
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
  printf("size(tuple) = %d\n", sizeof(struct tuple));
    assert(argc > 1);
    int workerid = atoi(argv[1]);
    struct worker * workers = get_workers();
    executor = workers[workerid].executors;
    //init_task2executor(executor);

    init(argv);
    printf("main: workerid = %d\n", workerid);

    pthread_t threads[MAX_EXECUTORS];
    for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
        printf("main: executor[%d] = %p\n", i, &executor[i]);
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

    int wait = 10;
    while(1) {
      sleep(wait);
#if 1 //def QUEUE_STAT
	for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
	  struct executor *self = &executor[i];
	  if(self->numexecutes-self->lastnumexecutes) {
	    printf("%d: numexecutes %zu, time %zu\n", self->taskid, 
		   self->numexecutes-self->lastnumexecutes, 
		   (self->execute_time-self->lastexecute_time) / (self->numexecutes - self->lastnumexecutes));
	    self->lastnumexecutes = self->numexecutes;
	    self->lastexecute_time = self->execute_time;
	  }
	}
#endif
    }

    return 0;
}
