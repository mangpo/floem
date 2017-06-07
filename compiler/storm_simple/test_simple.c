#include "simple.h"

int main(int argc, char *argv[]) {
    assert(argc > 1);
    int workerid = atoi(argv[1]);
    struct executor *executor = workers[workerid].executors;
    init_task2executor(executor);

    init(argv);
    printf("main: workerid = %d\n", workerid);

    for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
        printf("main: executor[%d] = %u\n", i, &executor[i]);
        if(executor[i].init != NULL)
            executor[i].init(&executor[i]);
    }

    run_threads();
    for(;;) {
        for(int i = 0; i < MAX_EXECUTORS && executor[i].execute != NULL; i++) {
            if(executor[i].spout) {
                spout_run(&executor[i]);
            }
        }
    }
    kill_threads();

    return 0;
}
