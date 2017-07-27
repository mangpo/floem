#include <stdio.h>
#include "worker.h"

struct executor *task2executor[MAX_TASKS];
int task2executorid[MAX_TASKS];
int task2worker[MAX_TASKS];
struct executor *my_executors;

void init_task2executor(struct executor *executor) {
  my_executors = executor;

  for(int i = 0; i < MAX_TASKS; i++) {
    task2executorid[i] = -1;
    task2worker[i] = -1;
  }
  for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
    printf("init: executor[%d] = %p, taskid = %d\n", i, &executor[i], executor[i].taskid);
    assert(task2executor[executor[i].taskid] == NULL);
    task2executor[executor[i].taskid] = &executor[i];
    task2executorid[executor[i].taskid] = i;
  }
  for(int i = 0; i < MAX_WORKERS && workers[i].hostname != NULL; i++) {
    for(int j = 0; j < MAX_EXECUTORS && workers[i].executors[j].execute != NULL; j++) {
      task2worker[workers[i].executors[j].taskid] = i;
    }
  }
}

int *get_task2executorid() {
  return task2executorid;
}

int *get_task2worker() {
  return task2worker;
}

struct executor *get_executors() {
  return my_executors;
}

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
