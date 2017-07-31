#include "storm.h"
#include "worker.h"
#include "dpdk.h"

struct executor *executor;

int main(int argc, char *argv[]) {
  //printf("size  = %d\n", sizeof(struct tuple));
  //exit(1);
    assert(argc > 1);
    //int workerid = atoi(argv[1]);
    //executor = workers[workerid].executors;
    //init_task2executor(executor);

    init(argv);
    while(1) dccp_print_stat();
/*
    DccpInfo* info = get_dccp_stat();

    size_t lasttuples = 0, tuples;
    run_threads();
    while(1) {
        sleep(1);
        __sync_synchronize();
	struct connection* connections = info->connections;
        for(int i = 0; i < MAX_WORKERS; i++) {
            printf("pipe,cwnd,acks,lastack[%d] = %u, %u, %zu, %d\n", i,
            connections[i].pipe, connections[i].cwnd, connections[i].acks, connections[i].lastack);
        }
        tuples = info->tuples - lasttuples;
        lasttuples = info->tuples;
        printf("acks sent %zu, rtt %" PRIu64 "\n", info->acks_sent, info->link_rtt);
        printf("Tuples/s: %zu, Gbits/s: %.2f\n\n",
           tuples, (tuples * sizeof(struct tuple) * 8) / 1000000000.0);
    }
    */
    kill_threads();

    return 0;
}
