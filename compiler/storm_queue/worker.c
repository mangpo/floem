#include "worker.h"

struct executor *task2executor[MAX_TASKS];
int task2executorid[MAX_TASKS];

void init_task2executor(struct executor *executor) {
  for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
    printf("init: executor[%d] = %u, taskid = %d\n", i, &executor[i], executor[i].taskid);
    assert(task2executor[executor[i].taskid] == NULL);
    task2executor[executor[i].taskid] = &executor[i];
    task2executorid[executor[i].taskid] = i;
  }
}

int *get_task2executorid() {
  return task2executorid;
}

struct tuple* random_tuple(size_t i) {
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
