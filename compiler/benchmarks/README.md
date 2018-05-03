Modified library files:
- include/queue.h
- include_cavium/floem-queue.*
- include_cavium/floem-queue-manage.*

To use CPU->NIC notify queue for NIC->CPU, modify app.c and CAVIUM.c generated from Inqueue.py as follows.

app.c
-----
circular_queue_lock* manager_queue;

rx_queue_Storage* manage_storage = (rx_queue_Storage *) shm_p;
shm_p = shm_p + MANAGE_SIZE;

memset(manage_storage, 0, MANAGE_SIZE);
manager_queue = init_manager_queue((void*) manage_storage);

circular_queue0->n1 = circular_queue0->len/circular_queue0->entry_size/2;
circular_queue0->n2 = circular_queue0->len/circular_queue0->entry_size - circular_queue0->n1;

dequeue_release(buf, 0, manager_queue);

CAVIUM.c
--------
rx_queue_Storage* manage_storage = (rx_queue_Storage *) shm_p;
shm_p = shm_p + MANAGE_SIZE;

if(corenum == 0) {
    init_manager_queue((void*) manage_storage);
}

circular_queue_lock0->id = create_dma_circular_queue((uint64_t) rx_queue_Storage0, sizeof(rx_queue_Storage), 64, enqueue_ready_var, enqueue_done_var, true);

if(corenum == RUNTIME_START_CORE) check_manager_queue();


Storm app.c (additional)
------------------------
q_buffer tmp = {(void*) x, 0, p};

void inqueue_advance_Release0(q_buffer buff) {
     struct tuple* x = (struct tuple*) buff.entry;
     if(x) {
     	   x->status = 0;
	   __SYNC;
	   dequeue_manage(buff, manager_queue);
     }
}

//assert(entry->status == 0);

