#include "storm.h"
#include "worker.h"
#include "dpdk.h"

struct executor *executor;

int main(int argc, char *argv[]) {
    assert(argc > 1);

    init(argv);
    run_threads();
    while(1) dccp_print_stat();
    kill_threads();

    return 0;
}
