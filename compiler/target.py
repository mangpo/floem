# device = CPU
HOST = 'CPU'
CPU = 'CPU'
cpu_include_h = ["<stdint.h>", "<stdbool.h>", "<stdio.h>", "<stdlib.h>", '"queue.h"']
cpu_include_c = ["<stdint.h>", "<stdbool.h>", "<stdio.h>", "<stdlib.h>", "<string.h>", "<stddef.h>", "<unistd.h>", "<pthread.h>",
                 '"queue.h"', '"shm.h"' ] #, '"dpdk.h"']

# device = CAVIUM, process = CAVIUM
CAVIUM = 'CAVIUM'
cavium_include_h = ['"cvmcs-nic.h"', '"cvmcs-queue.h"']
cavium_include_c = ['<cvmx-atomic.h>', '"cvmcs-nic.h"', '"cvmcs-dma.h"', '"cvmcs-queue.h"']

# device = CPU, process = DPDK
def is_dpdk_proc(process):
    return process == 'dpdk'

dpdk_base = "/opt/dpdk/"
#dpdk_include = dpdk_base + "/include/dpdk"
dpdk_include = "/home/mangpo/lib/dpdk-16.11/build/include"
dpdk_lib = dpdk_base + "/lib/"
dpdk_pmds = "-lrte_pmd_ixgbe -lrte_pmd_i40e"
dpdk_libs = "-Wl,--whole-archive " + dpdk_pmds + " -lrte_eal" + \
    " -lrte_mempool -lrte_mempool_ring -lrte_hash -lrte_ring -lrte_kvargs" + \
    " -lrte_ethdev -lrte_mbuf -lrte_pmd_ring -Wl,--no-whole-archive -lm" + \
    " -lpthread -lrt -ldl"
dpdk_driver_header = ["<dpdk.h>", '"dpdkif.h"']
