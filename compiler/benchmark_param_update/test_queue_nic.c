#include "app.h"
#include "protocol_binary.h"

int main(int argc, char *argv[]) {
    init(argv);
    run_threads();
    while(1) pause();
    kill_threads();
}