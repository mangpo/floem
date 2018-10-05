# Queue Synchronization Layer

If you are interested in using our queue synchronization layer with your own queue implementation.
First read Section 3.6 of my [thesis](http://www2.eecs.berkeley.edu/Pubs/TechRpts/2018/EECS-2018-134.html).

The queue synchronization layer is in `floem/include_cavium/floem-queue-manage`. 
The functions `smart_dma_read` and `smart_dma_write` in `floem-queue-manage.c` is equivalent to the functions `access_entry` and `access_done`, explained in the document, respectively.

Our NIC queue implementation is in `floem/include_cavium/floem-queue`. 
The functions `enqueue_ready_var` and `dequeue_ready_var` are the function `nic_own` for enqueue and dequeue processes, respectively,
while `enqueue_done_var` and `dequeue_done_var` are `cpu_own` for enqueue and dequeue processes, respectively.

Our CPU queue implementation is in `floem/include/queue.h`.