#include "test_compare.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <pthread.h>


#include <rte_memcpy.h>
#include "nicif.h"
#include "iokvs.h"
#include "protocol_binary.h"
#include "../queue.h"

inject_state* _spec_inject_state_inst;

probe_state* _spec_probe_state_inst;

segments_holder* _impl_segments_holder2;

last_segment* _impl_last_segment3;

_table_iokvs_message$_256* _impl__table_msg_put_creator;

inject_state* _impl_inject_state_inst;

probe_state* _impl_probe_state_inst;

_rx_queue_queue_dummy* _impl_memcached__rx_queue_queue_dummy0;

_rx_queue_queue_dummy* _impl_memcached__rx_queue_queue_dummy1;

_rx_queue_queue_dummy* _impl_memcached__rx_queue_queue_dummy2;

_rx_queue_queue_dummy* _impl_memcached__rx_queue_queue_dummy3;

circular_queue* _impl_memcached__rx_queue_queue_inst0;

circular_queue* _impl_memcached__rx_queue_queue_inst1;

circular_queue* _impl_memcached__rx_queue_queue_inst2;

circular_queue* _impl_memcached__rx_queue_queue_inst3;

circular_queue* _impl_memcached__rx_queue_queue_deq_inst0;

circular_queue* _impl_memcached__rx_queue_queue_deq_inst1;

circular_queue* _impl_memcached__rx_queue_queue_deq_inst2;

circular_queue* _impl_memcached__rx_queue_queue_deq_inst3;

_rx_queue_queues* _impl_memcached__rx_queue_queues_inst;

_rx_queue_queues* _impl_memcached__rx_queue_queues_deq_inst;

_tx_queue_queue_dummy* _impl_memcached__tx_queue_queue_dummy0;

_tx_queue_queue_dummy* _impl_memcached__tx_queue_queue_dummy1;

_tx_queue_queue_dummy* _impl_memcached__tx_queue_queue_dummy2;

_tx_queue_queue_dummy* _impl_memcached__tx_queue_queue_dummy3;

circular_queue* _impl_memcached__tx_queue_queue_inst0;

circular_queue* _impl_memcached__tx_queue_queue_inst1;

circular_queue* _impl_memcached__tx_queue_queue_inst2;

circular_queue* _impl_memcached__tx_queue_queue_inst3;

circular_queue* _impl_memcached__tx_queue_queue_deq_inst0;

circular_queue* _impl_memcached__tx_queue_queue_deq_inst1;

circular_queue* _impl_memcached__tx_queue_queue_deq_inst2;

circular_queue* _impl_memcached__tx_queue_queue_deq_inst3;

_tx_queue_queues* _impl_memcached__tx_queue_queues_inst;

_tx_queue_queues* _impl_memcached__tx_queue_queues_deq_inst;

size_t shm_size = 0;
void *shm;
void init_state_instances(char *argv[]) {

_spec_inject_state_inst = (inject_state *) malloc(sizeof(inject_state));
memset(_spec_inject_state_inst, 0, sizeof(inject_state));

_spec_inject_state_inst->p = 0;

_spec_probe_state_inst = (probe_state *) malloc(sizeof(probe_state));
memset(_spec_probe_state_inst, 0, sizeof(probe_state));

_spec_probe_state_inst->p = 0;

_impl_segments_holder2 = (segments_holder *) malloc(sizeof(segments_holder));
memset(_impl_segments_holder2, 0, sizeof(segments_holder));

_impl_segments_holder2->segbase = 0;
_impl_segments_holder2->seglen = 0;
_impl_segments_holder2->offset = 0;
_impl_segments_holder2->next = 0;

_impl_last_segment3 = (last_segment *) malloc(sizeof(last_segment));
memset(_impl_last_segment3, 0, sizeof(last_segment));

_impl_last_segment3->holder = 0;

_impl__table_msg_put_creator = (_table_iokvs_message$_256 *) malloc(sizeof(_table_iokvs_message$_256));
memset(_impl__table_msg_put_creator, 0, sizeof(_table_iokvs_message$_256));


_impl_inject_state_inst = (inject_state *) malloc(sizeof(inject_state));
memset(_impl_inject_state_inst, 0, sizeof(inject_state));

_impl_inject_state_inst->p = 0;

_impl_probe_state_inst = (probe_state *) malloc(sizeof(probe_state));
memset(_impl_probe_state_inst, 0, sizeof(probe_state));

_impl_probe_state_inst->p = 0;

_impl_memcached__rx_queue_queue_dummy0 = (_rx_queue_queue_dummy *) malloc(sizeof(_rx_queue_queue_dummy));
memset(_impl_memcached__rx_queue_queue_dummy0, 0, sizeof(_rx_queue_queue_dummy));


_impl_memcached__rx_queue_queue_dummy1 = (_rx_queue_queue_dummy *) malloc(sizeof(_rx_queue_queue_dummy));
memset(_impl_memcached__rx_queue_queue_dummy1, 0, sizeof(_rx_queue_queue_dummy));


_impl_memcached__rx_queue_queue_dummy2 = (_rx_queue_queue_dummy *) malloc(sizeof(_rx_queue_queue_dummy));
memset(_impl_memcached__rx_queue_queue_dummy2, 0, sizeof(_rx_queue_queue_dummy));


_impl_memcached__rx_queue_queue_dummy3 = (_rx_queue_queue_dummy *) malloc(sizeof(_rx_queue_queue_dummy));
memset(_impl_memcached__rx_queue_queue_dummy3, 0, sizeof(_rx_queue_queue_dummy));


_impl_memcached__rx_queue_queue_inst0 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_inst0, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_inst0->len = 10000;
_impl_memcached__rx_queue_queue_inst0->offset = 0;
_impl_memcached__rx_queue_queue_inst0->queue = _impl_memcached__rx_queue_queue_dummy0;

_impl_memcached__rx_queue_queue_inst1 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_inst1, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_inst1->len = 10000;
_impl_memcached__rx_queue_queue_inst1->offset = 0;
_impl_memcached__rx_queue_queue_inst1->queue = _impl_memcached__rx_queue_queue_dummy1;

_impl_memcached__rx_queue_queue_inst2 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_inst2, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_inst2->len = 10000;
_impl_memcached__rx_queue_queue_inst2->offset = 0;
_impl_memcached__rx_queue_queue_inst2->queue = _impl_memcached__rx_queue_queue_dummy2;

_impl_memcached__rx_queue_queue_inst3 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_inst3, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_inst3->len = 10000;
_impl_memcached__rx_queue_queue_inst3->offset = 0;
_impl_memcached__rx_queue_queue_inst3->queue = _impl_memcached__rx_queue_queue_dummy3;

_impl_memcached__rx_queue_queue_deq_inst0 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_deq_inst0, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_deq_inst0->len = 10000;
_impl_memcached__rx_queue_queue_deq_inst0->offset = 0;
_impl_memcached__rx_queue_queue_deq_inst0->queue = _impl_memcached__rx_queue_queue_dummy0;

_impl_memcached__rx_queue_queue_deq_inst1 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_deq_inst1, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_deq_inst1->len = 10000;
_impl_memcached__rx_queue_queue_deq_inst1->offset = 0;
_impl_memcached__rx_queue_queue_deq_inst1->queue = _impl_memcached__rx_queue_queue_dummy1;

_impl_memcached__rx_queue_queue_deq_inst2 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_deq_inst2, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_deq_inst2->len = 10000;
_impl_memcached__rx_queue_queue_deq_inst2->offset = 0;
_impl_memcached__rx_queue_queue_deq_inst2->queue = _impl_memcached__rx_queue_queue_dummy2;

_impl_memcached__rx_queue_queue_deq_inst3 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__rx_queue_queue_deq_inst3, 0, sizeof(circular_queue));

_impl_memcached__rx_queue_queue_deq_inst3->len = 10000;
_impl_memcached__rx_queue_queue_deq_inst3->offset = 0;
_impl_memcached__rx_queue_queue_deq_inst3->queue = _impl_memcached__rx_queue_queue_dummy3;

_impl_memcached__rx_queue_queues_inst = (_rx_queue_queues *) malloc(sizeof(_rx_queue_queues));
memset(_impl_memcached__rx_queue_queues_inst, 0, sizeof(_rx_queue_queues));

_impl_memcached__rx_queue_queues_inst->cores[0] = _impl_memcached__rx_queue_queue_inst0;
_impl_memcached__rx_queue_queues_inst->cores[1] = _impl_memcached__rx_queue_queue_inst1;
_impl_memcached__rx_queue_queues_inst->cores[2] = _impl_memcached__rx_queue_queue_inst2;
_impl_memcached__rx_queue_queues_inst->cores[3] = _impl_memcached__rx_queue_queue_inst3;

_impl_memcached__rx_queue_queues_deq_inst = (_rx_queue_queues *) malloc(sizeof(_rx_queue_queues));
memset(_impl_memcached__rx_queue_queues_deq_inst, 0, sizeof(_rx_queue_queues));

_impl_memcached__rx_queue_queues_deq_inst->cores[0] = _impl_memcached__rx_queue_queue_deq_inst0;
_impl_memcached__rx_queue_queues_deq_inst->cores[1] = _impl_memcached__rx_queue_queue_deq_inst1;
_impl_memcached__rx_queue_queues_deq_inst->cores[2] = _impl_memcached__rx_queue_queue_deq_inst2;
_impl_memcached__rx_queue_queues_deq_inst->cores[3] = _impl_memcached__rx_queue_queue_deq_inst3;

_impl_memcached__tx_queue_queue_dummy0 = (_tx_queue_queue_dummy *) malloc(sizeof(_tx_queue_queue_dummy));
memset(_impl_memcached__tx_queue_queue_dummy0, 0, sizeof(_tx_queue_queue_dummy));


_impl_memcached__tx_queue_queue_dummy1 = (_tx_queue_queue_dummy *) malloc(sizeof(_tx_queue_queue_dummy));
memset(_impl_memcached__tx_queue_queue_dummy1, 0, sizeof(_tx_queue_queue_dummy));


_impl_memcached__tx_queue_queue_dummy2 = (_tx_queue_queue_dummy *) malloc(sizeof(_tx_queue_queue_dummy));
memset(_impl_memcached__tx_queue_queue_dummy2, 0, sizeof(_tx_queue_queue_dummy));


_impl_memcached__tx_queue_queue_dummy3 = (_tx_queue_queue_dummy *) malloc(sizeof(_tx_queue_queue_dummy));
memset(_impl_memcached__tx_queue_queue_dummy3, 0, sizeof(_tx_queue_queue_dummy));


_impl_memcached__tx_queue_queue_inst0 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_inst0, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_inst0->len = 10000;
_impl_memcached__tx_queue_queue_inst0->offset = 0;
_impl_memcached__tx_queue_queue_inst0->queue = _impl_memcached__tx_queue_queue_dummy0;

_impl_memcached__tx_queue_queue_inst1 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_inst1, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_inst1->len = 10000;
_impl_memcached__tx_queue_queue_inst1->offset = 0;
_impl_memcached__tx_queue_queue_inst1->queue = _impl_memcached__tx_queue_queue_dummy1;

_impl_memcached__tx_queue_queue_inst2 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_inst2, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_inst2->len = 10000;
_impl_memcached__tx_queue_queue_inst2->offset = 0;
_impl_memcached__tx_queue_queue_inst2->queue = _impl_memcached__tx_queue_queue_dummy2;

_impl_memcached__tx_queue_queue_inst3 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_inst3, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_inst3->len = 10000;
_impl_memcached__tx_queue_queue_inst3->offset = 0;
_impl_memcached__tx_queue_queue_inst3->queue = _impl_memcached__tx_queue_queue_dummy3;

_impl_memcached__tx_queue_queue_deq_inst0 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_deq_inst0, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_deq_inst0->len = 10000;
_impl_memcached__tx_queue_queue_deq_inst0->offset = 0;
_impl_memcached__tx_queue_queue_deq_inst0->queue = _impl_memcached__tx_queue_queue_dummy0;

_impl_memcached__tx_queue_queue_deq_inst1 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_deq_inst1, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_deq_inst1->len = 10000;
_impl_memcached__tx_queue_queue_deq_inst1->offset = 0;
_impl_memcached__tx_queue_queue_deq_inst1->queue = _impl_memcached__tx_queue_queue_dummy1;

_impl_memcached__tx_queue_queue_deq_inst2 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_deq_inst2, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_deq_inst2->len = 10000;
_impl_memcached__tx_queue_queue_deq_inst2->offset = 0;
_impl_memcached__tx_queue_queue_deq_inst2->queue = _impl_memcached__tx_queue_queue_dummy2;

_impl_memcached__tx_queue_queue_deq_inst3 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_impl_memcached__tx_queue_queue_deq_inst3, 0, sizeof(circular_queue));

_impl_memcached__tx_queue_queue_deq_inst3->len = 10000;
_impl_memcached__tx_queue_queue_deq_inst3->offset = 0;
_impl_memcached__tx_queue_queue_deq_inst3->queue = _impl_memcached__tx_queue_queue_dummy3;

_impl_memcached__tx_queue_queues_inst = (_tx_queue_queues *) malloc(sizeof(_tx_queue_queues));
memset(_impl_memcached__tx_queue_queues_inst, 0, sizeof(_tx_queue_queues));

_impl_memcached__tx_queue_queues_inst->cores[0] = _impl_memcached__tx_queue_queue_inst0;
_impl_memcached__tx_queue_queues_inst->cores[1] = _impl_memcached__tx_queue_queue_inst1;
_impl_memcached__tx_queue_queues_inst->cores[2] = _impl_memcached__tx_queue_queue_inst2;
_impl_memcached__tx_queue_queues_inst->cores[3] = _impl_memcached__tx_queue_queue_inst3;

_impl_memcached__tx_queue_queues_deq_inst = (_tx_queue_queues *) malloc(sizeof(_tx_queue_queues));
memset(_impl_memcached__tx_queue_queues_deq_inst, 0, sizeof(_tx_queue_queues));

_impl_memcached__tx_queue_queues_deq_inst->cores[0] = _impl_memcached__tx_queue_queue_deq_inst0;
_impl_memcached__tx_queue_queues_deq_inst->cores[1] = _impl_memcached__tx_queue_queue_deq_inst1;
_impl_memcached__tx_queue_queues_deq_inst->cores[2] = _impl_memcached__tx_queue_queue_deq_inst2;
_impl_memcached__tx_queue_queues_deq_inst->cores[3] = _impl_memcached__tx_queue_queue_deq_inst3;

}

void finalize_state_instances() {

}

void __impl_prepare_get_response_join_buffer_in_packet_save(__impl_prepare_get_response_join_buffer *p, iokvs_message* in_packet_arg0) {
  p->in_packet_arg0 = in_packet_arg0;
}
void __impl_prepare_get_response_join_buffer_in_item_save(__impl_prepare_get_response_join_buffer *p, item* in_item_arg0) {
  p->in_item_arg0 = in_item_arg0;
}

void __impl_memcached_enq_alloc_get_join_buffer_in_len_save(__impl_memcached_enq_alloc_get_join_buffer *p, size_t in_len_arg0) {
  p->in_len_arg0 = in_len_arg0;
}
void __impl_memcached_enq_alloc_get_join_buffer_in_core_save(__impl_memcached_enq_alloc_get_join_buffer *p, size_t in_core_arg0) {
  p->in_core_arg0 = in_core_arg0;
}

void __impl_fill_eqe_full_join_buffer_in_entry_save(__impl_fill_eqe_full_join_buffer *p, q_entry* in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void __impl_fill_eqe_full_join_buffer_in_segment_save(__impl_fill_eqe_full_join_buffer *p, uint64_t in_segment_arg0) {
  p->in_segment_arg0 = in_segment_arg0;
}

void __impl_memcached_enq_alloc_full_join_buffer_in_len_save(__impl_memcached_enq_alloc_full_join_buffer *p, size_t in_len_arg0) {
  p->in_len_arg0 = in_len_arg0;
}
void __impl_memcached_enq_alloc_full_join_buffer_in_core_save(__impl_memcached_enq_alloc_full_join_buffer *p, size_t in_core_arg0) {
  p->in_core_arg0 = in_core_arg0;
}

void __spec_prepare_get_response_join_buffer_in_packet_save(__spec_prepare_get_response_join_buffer *p, iokvs_message* in_packet_arg0) {
  p->in_packet_arg0 = in_packet_arg0;
}
void __spec_prepare_get_response_join_buffer_in_item_save(__spec_prepare_get_response_join_buffer *p, item* in_item_arg0) {
  p->in_item_arg0 = in_item_arg0;
}

void __impl_classifier_join_buffer_in_pkt_save(__impl_classifier_join_buffer *p, iokvs_message* in_pkt_arg0) {
  p->in_pkt_arg0 = in_pkt_arg0;
}
void __impl_classifier_join_buffer_in_hash_save(__impl_classifier_join_buffer *p, void* in_hash_arg0, size_t in_hash_arg1, uint32_t in_hash_arg2) {
  p->in_hash_arg0 = in_hash_arg0;
  p->in_hash_arg1 = in_hash_arg1;
  p->in_hash_arg2 = in_hash_arg2;
}

void __impl_memcached_enq_alloc_set_join_buffer_in_len_save(__impl_memcached_enq_alloc_set_join_buffer *p, size_t in_len_arg0) {
  p->in_len_arg0 = in_len_arg0;
}
void __impl_memcached_enq_alloc_set_join_buffer_in_core_save(__impl_memcached_enq_alloc_set_join_buffer *p, size_t in_core_arg0) {
  p->in_core_arg0 = in_core_arg0;
}

void __spec_get_item_spec_join_buffer_in_pkt_save(__spec_get_item_spec_join_buffer *p, iokvs_message* in_pkt_arg0) {
  p->in_pkt_arg0 = in_pkt_arg0;
}
void __spec_get_item_spec_join_buffer_in_hash_save(__spec_get_item_spec_join_buffer *p, void* in_hash_arg0, size_t in_hash_arg1, uint32_t in_hash_arg2) {
  p->in_hash_arg0 = in_hash_arg0;
  p->in_hash_arg1 = in_hash_arg1;
  p->in_hash_arg2 = in_hash_arg2;
}

void __impl_fill_eqe_set_join_buffer_in_entry_save(__impl_fill_eqe_set_join_buffer *p, q_entry* in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void __impl_fill_eqe_set_join_buffer_in_item_save(__impl_fill_eqe_set_join_buffer *p, item* in_item_arg0, uint64_t in_item_arg1) {
  p->in_item_arg0 = in_item_arg0;
  p->in_item_arg1 = in_item_arg1;
}

void __spec_classifier_join_buffer_in_pkt_save(__spec_classifier_join_buffer *p, iokvs_message* in_pkt_arg0) {
  p->in_pkt_arg0 = in_pkt_arg0;
}
void __spec_classifier_join_buffer_in_hash_save(__spec_classifier_join_buffer *p, void* in_hash_arg0, size_t in_hash_arg1, uint32_t in_hash_arg2) {
  p->in_hash_arg0 = in_hash_arg0;
  p->in_hash_arg1 = in_hash_arg1;
  p->in_hash_arg2 = in_hash_arg2;
}

void __impl_msg_put_join_buffer_in_index_save(__impl_msg_put_join_buffer *p, uint64_t in_index_arg0) {
  p->in_index_arg0 = in_index_arg0;
}
void __impl_msg_put_join_buffer_in_value_save(__impl_msg_put_join_buffer *p, iokvs_message* in_value_arg0) {
  p->in_value_arg0 = in_value_arg0;
}

void __impl_fill_eqe_get_join_buffer_in_entry_save(__impl_fill_eqe_get_join_buffer *p, q_entry* in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void __impl_fill_eqe_get_join_buffer_in_pkt_hash_save(__impl_fill_eqe_get_join_buffer *p, iokvs_message* in_pkt_hash_arg0, void* in_pkt_hash_arg1, size_t in_pkt_hash_arg2, uint32_t in_pkt_hash_arg3) {
  p->in_pkt_hash_arg0 = in_pkt_hash_arg0;
  p->in_pkt_hash_arg1 = in_pkt_hash_arg1;
  p->in_pkt_hash_arg2 = in_pkt_hash_arg2;
  p->in_pkt_hash_arg3 = in_pkt_hash_arg3;
}

void __impl_fill_cqe_join_buffer_in_entry_save(__impl_fill_cqe_join_buffer *p, q_entry* in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void __impl_fill_cqe_join_buffer_in_type_save(__impl_fill_cqe_join_buffer *p, uint8_t in_type_arg0) {
  p->in_type_arg0 = in_type_arg0;
}
void __impl_fill_cqe_join_buffer_in_pointer_save(__impl_fill_cqe_join_buffer *p, uint64_t in_pointer_arg0) {
  p->in_pointer_arg0 = in_pointer_arg0;
}
void __impl_fill_cqe_join_buffer_in_size_save(__impl_fill_cqe_join_buffer *p, uint64_t in_size_arg0) {
  p->in_size_arg0 = in_size_arg0;
}
void __impl_fill_cqe_join_buffer_in_opaque_save(__impl_fill_cqe_join_buffer *p, uint64_t in_opaque_arg0) {
  p->in_opaque_arg0 = in_opaque_arg0;
}

void __impl_memcached__tx_queue_enqueue_alloc_join_buffer_in_core_save(__impl_memcached__tx_queue_enqueue_alloc_join_buffer *p, size_t in_core_arg0) {
  p->in_core_arg0 = in_core_arg0;
}
void __impl_memcached__tx_queue_enqueue_alloc_join_buffer_in_len_save(__impl_memcached__tx_queue_enqueue_alloc_join_buffer *p, size_t in_len_arg0) {
  p->in_len_arg0 = in_len_arg0;
}

#define _get_q_entry$(X) X
void _spec_Jenkins_Hash(__spec_classifier_join_buffer*,void*,size_t);
void _spec_inject_inst0();
void _impl_get_item(__impl_fill_eqe_set_join_buffer*,iokvs_message*,void*,size_t,uint32_t);
void _impl_prepare_get_response(iokvs_message*,item*);
void _impl_memcached_enq_alloc_get(__impl_fill_eqe_get_join_buffer*,size_t,size_t);
void _impl_fill_eqe_full(q_entry*,uint64_t);
void _impl_memcached_enq_alloc_full(__impl_fill_eqe_full_join_buffer*,size_t,size_t);
void _impl_memcached_identiy67(size_t,uint8_t,uint64_t,uint64_t,uint64_t);
void _impl_inject_inst0_out_fork5_inst(iokvs_message*);
void _impl_probe0(iokvs_message*);
void _impl_probe1(iokvs_message*);
q_entry* _impl_memcached__rx_queue_dequeue_get0(size_t);
void _spec_insert_item(item*);
void _impl_memcached__tx_queue_dequeue_get();
void _impl_GetKey(__impl_classifier_join_buffer*,iokvs_message*);
void _spec_probe1(iokvs_message*);
void _spec_probe0(iokvs_message*);
void _spec_prepare_get_response(iokvs_message*,item*);
void _impl_unpack_set(cqe_send_setresponse*);
void _impl_filter_full_out_fork4_inst(uint64_t);
void _impl_msg_get_get(__impl_prepare_get_response_join_buffer*,uint64_t);
void _impl_inject_inst0();
void _impl_memcached__tx_queue_enqueue_submit(q_entry*);
void _impl_len_set(__impl_memcached_enq_alloc_set_join_buffer*,__impl_fill_eqe_set_join_buffer*,iokvs_message*,void*,size_t,uint32_t);
void _impl_classifier(iokvs_message*,void*,size_t,uint32_t);
void _impl_memcached_enq_alloc_set(__impl_fill_eqe_set_join_buffer*,size_t,size_t);
void _impl_print_msg(iokvs_message*);
void _impl_memcached__rx_queue_enqueue_submit_ele4(q_entry*);
void _impl_len_get(__impl_memcached_enq_alloc_get_join_buffer*,__impl_fill_eqe_get_join_buffer*,iokvs_message*,void*,size_t,uint32_t);
void _spec_print_msg(iokvs_message*);
void _spec_inject_inst0_out_fork0_inst(iokvs_message*);
void _impl_len_core_set(__impl_fill_eqe_full_join_buffer*,uint64_t);
void _impl_memcached__rx_queue_dequeue_release_ele5(q_entry*);
void _spec_get_item_spec(iokvs_message*,void*,size_t,uint32_t);
void _impl_add_logseg(cqe_add_logseg*);
void _spec_prepare_set_response(iokvs_message*);
void _impl_fill_eqe_set(q_entry*,item*,uint64_t);
void _impl_classifier_out_get_fork6_inst(iokvs_message*,void*,size_t,uint32_t);
void _spec_classifier(iokvs_message*,void*,size_t,uint32_t);
void _impl_msg_put(uint64_t,iokvs_message*);
void _spec_extract_pkt_hash1_out_pkt_fork1_inst(__spec_get_item_spec_join_buffer*,iokvs_message*);
void _impl_len_cqe(__impl_fill_cqe_join_buffer*,__impl_memcached__tx_queue_enqueue_alloc_join_buffer*,uint8_t);
void _impl_get_core_get(__impl_memcached_enq_alloc_get_join_buffer*,__impl_fill_eqe_get_join_buffer*,iokvs_message*,void*,size_t,uint32_t);
void _spec_GetKey(__spec_classifier_join_buffer*,iokvs_message*);
void _impl_fill_eqe_get(q_entry*,iokvs_message*,void*,size_t,uint32_t);
void _impl_filter_full(uint64_t);
void _spec_Lookup(__spec_prepare_get_response_join_buffer*,void*,size_t,uint32_t);
void _impl_prepare_set_response(iokvs_message*);
void _impl_unpack_get(cqe_send_getresponse*);
void _impl_fill_cqe(q_entry*,uint8_t,uint64_t,uint64_t,uint64_t);
void _impl_get_core_set(__impl_memcached_enq_alloc_set_join_buffer*,__impl_fill_eqe_set_join_buffer*,iokvs_message*,void*,size_t,uint32_t);
void _impl_Jenkins_Hash(__impl_classifier_join_buffer*,void*,size_t);
void _impl_classifier_out_set_fork2_inst(iokvs_message*,void*,size_t,uint32_t);
void _impl_classifier_rx(q_entry*);
void _impl_memcached__tx_queue_dequeue_release(q_entry*);
void _impl_memcached__tx_queue_enqueue_alloc(__impl_fill_cqe_join_buffer*,size_t,size_t);
void _spec_extract_pkt_hash0(iokvs_message*,void*,size_t,uint32_t);
void _spec_extract_pkt_hash1(iokvs_message*,void*,size_t,uint32_t);
void _impl_GetOpaque(__impl_msg_put_join_buffer*,iokvs_message*);
void _impl_msg_get_set(uint64_t);
void _impl_memcached_identiy67_out1_fork3_inst(__impl_fill_cqe_join_buffer*,__impl_memcached__tx_queue_enqueue_alloc_join_buffer*,uint8_t);
void _spec_Jenkins_Hash(__spec_classifier_join_buffer* _p__spec_classifier, void* key,  size_t length) {

uint32_t hash = jenkins_hash(key, length);

  __spec_classifier_join_buffer_in_hash_save(_p__spec_classifier, key, length, hash);  _spec_classifier(_p__spec_classifier->in_pkt_arg0, _p__spec_classifier->in_hash_arg0, _p__spec_classifier->in_hash_arg1, _p__spec_classifier->in_hash_arg2);

}

void _spec_inject_inst0() {
  
        if(_spec_inject_state_inst->p >= 1000) { printf("Error: inject more than available entries.\n"); exit(-1); }
        int temp = _spec_inject_state_inst->p;
        _spec_inject_state_inst->p++;
  _spec_inject_inst0_out_fork0_inst(_spec_inject_state_inst->data[temp]);
}

void _impl_get_item(__impl_fill_eqe_set_join_buffer* _p__impl_fill_eqe_set, iokvs_message* m,  void* key,  size_t keylen,  uint32_t hash) {

    size_t totlen = m->mcr.request.bodylen - m->mcr.request.extlen;

    uint64_t full = 0;
    item *it = segment_item_alloc(_impl_segments_holder2->segbase, _impl_segments_holder2->seglen, &_impl_segments_holder2->offset, sizeof(item) + totlen);     if(it == NULL) {
        printf("Segment is full.\n");
        full = _impl_segments_holder2->segbase + _impl_segments_holder2->offset;
        _impl_segments_holder2->segbase = _impl_segments_holder2->next->segbase;
        _impl_segments_holder2->seglen = _impl_segments_holder2->next->seglen;
        _impl_segments_holder2->offset = _impl_segments_holder2->next->offset;
        _impl_segments_holder2->next = _impl_segments_holder2->next->next;
                it = segment_item_alloc(_impl_segments_holder2->segbase, _impl_segments_holder2->seglen, &_impl_segments_holder2->offset, sizeof(item) + totlen);
    }

    printf("get_item id: %d, keylen: %ld, hash: %d, totlen: %ld, item: %ld\n", m->mcr.request.magic, keylen, hash, totlen, it);
    it->hv = hash;
    it->vallen = totlen - keylen;
    it->keylen = keylen;
        rte_memcpy(item_key(it), key, totlen);

    
  __impl_fill_eqe_set_join_buffer_in_item_save(_p__impl_fill_eqe_set, it, m->mcr.request.magic);  _impl_fill_eqe_set(_p__impl_fill_eqe_set->in_entry_arg0, _p__impl_fill_eqe_set->in_item_arg0, _p__impl_fill_eqe_set->in_item_arg1);

  _impl_filter_full(full);
}

void _impl_prepare_get_response(iokvs_message* p, item* it) {

iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4 + it->vallen);
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
m->mcr.request.magic = p->mcr.request.magic;
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
if (it != NULL) {
  m->mcr.request.bodylen = 4 + it->vallen;
  rte_memcpy(m->payload + 4, item_value(it), it->vallen);
}


  _impl_probe0(m);
}

void _impl_memcached_enq_alloc_get(__impl_fill_eqe_get_join_buffer* _p__impl_fill_eqe_get, size_t len, size_t c) {

           circular_queue *q = _impl_memcached__rx_queue_queues_inst->cores[c];
                      q_entry* entry = (q_entry*) enqueue_alloc(q, len);
                                 
  __impl_fill_eqe_get_join_buffer_in_entry_save(_p__impl_fill_eqe_get, entry);
}

void _impl_fill_eqe_full(q_entry* _x0, uint64_t full) {
  
eqe_seg_full* entry = (eqe_seg_full *) _x0;
entry->flags |= EQE_TYPE_SEGFULL << EQE_TYPE_SHIFT;
entry->last = full;

  _impl_memcached__rx_queue_enqueue_submit_ele4((q_entry*) entry);
}

void _impl_memcached_enq_alloc_full(__impl_fill_eqe_full_join_buffer* _p__impl_fill_eqe_full, size_t len, size_t c) {

           circular_queue *q = _impl_memcached__rx_queue_queues_inst->cores[c];
                      q_entry* entry = (q_entry*) enqueue_alloc(q, len);
                                 
  __impl_fill_eqe_full_join_buffer_in_entry_save(_p__impl_fill_eqe_full, entry);
}

void _impl_memcached_identiy67(size_t x0_0, uint8_t x1_0, uint64_t x2_0, uint64_t x3_0, uint64_t x4_0) {
  __impl_fill_cqe_join_buffer *_p__impl_fill_cqe = malloc(sizeof(__impl_fill_cqe_join_buffer));
  __impl_memcached__tx_queue_enqueue_alloc_join_buffer *_p__impl_memcached__tx_queue_enqueue_alloc = malloc(sizeof(__impl_memcached__tx_queue_enqueue_alloc_join_buffer));


  __impl_memcached__tx_queue_enqueue_alloc_join_buffer_in_core_save(_p__impl_memcached__tx_queue_enqueue_alloc, x0_0);
  _impl_memcached_identiy67_out1_fork3_inst(_p__impl_fill_cqe,_p__impl_memcached__tx_queue_enqueue_alloc,x1_0);
  __impl_fill_cqe_join_buffer_in_pointer_save(_p__impl_fill_cqe, x2_0);
  __impl_fill_cqe_join_buffer_in_size_save(_p__impl_fill_cqe, x3_0);
  __impl_fill_cqe_join_buffer_in_opaque_save(_p__impl_fill_cqe, x4_0);  _impl_fill_cqe(_p__impl_fill_cqe->in_entry_arg0, _p__impl_fill_cqe->in_type_arg0, _p__impl_fill_cqe->in_pointer_arg0, _p__impl_fill_cqe->in_size_arg0, _p__impl_fill_cqe->in_opaque_arg0);

}

void _impl_inject_inst0_out_fork5_inst(iokvs_message* _arg0) {
  __impl_classifier_join_buffer *_p__impl_classifier = malloc(sizeof(__impl_classifier_join_buffer));
  __impl_msg_put_join_buffer *_p__impl_msg_put = malloc(sizeof(__impl_msg_put_join_buffer));
 
  _impl_GetOpaque(_p__impl_msg_put,_arg0);
  __impl_msg_put_join_buffer_in_value_save(_p__impl_msg_put, _arg0);  _impl_msg_put(_p__impl_msg_put->in_index_arg0, _p__impl_msg_put->in_value_arg0);

  __impl_classifier_join_buffer_in_pkt_save(_p__impl_classifier, _arg0);
  _impl_GetKey(_p__impl_classifier,_arg0);
}

void _impl_probe0(iokvs_message* x) {
 
        if(_impl_probe_state_inst->p >= 1010) { printf("Error: probe more than available entries.\n"); exit(-1); }
        _impl_probe_state_inst->data[_impl_probe_state_inst->p] = x;
        _impl_probe_state_inst->p++; 
  _impl_print_msg(x);
}

void _impl_probe1(iokvs_message* x) {
 
        if(_impl_probe_state_inst->p >= 1010) { printf("Error: probe more than available entries.\n"); exit(-1); }
        _impl_probe_state_inst->data[_impl_probe_state_inst->p] = x;
        _impl_probe_state_inst->p++; 
  _impl_print_msg(x);
}

q_entry* _impl_memcached__rx_queue_dequeue_get0(size_t c) {

        circular_queue *q = _impl_memcached__rx_queue_queues_deq_inst->cores[c];
        q_entry* x = dequeue_get(q);
                
  q_entry* ret;
  ret = _get_q_entry$(x);
  return ret;
}

void _spec_insert_item(item *it) {

hasht_put(it, NULL);

}

void _impl_memcached__tx_queue_dequeue_get() {
  
        static int c = 0;          int n = 4;
        q_entry* x = NULL;
        for(int i=0; i<n; i++) {
            int index = (c + i) % n;
            circular_queue* q = _impl_memcached__tx_queue_queues_deq_inst->cores[index];
            x = dequeue_get(q);
            if(x != NULL) {
                c = (index + 1) % n;
                break;
            }
        }
        
  _impl_classifier_rx(x);
}

void _impl_GetKey(__impl_classifier_join_buffer* _p__impl_classifier, iokvs_message* m) {

void *key = m->payload + m->mcr.request.extlen;
size_t len = m->mcr.request.keylen;

  _impl_Jenkins_Hash(_p__impl_classifier,key, len);
}

void _spec_probe1(iokvs_message* x) {
 
        if(_spec_probe_state_inst->p >= 1010) { printf("Error: probe more than available entries.\n"); exit(-1); }
        _spec_probe_state_inst->data[_spec_probe_state_inst->p] = x;
        _spec_probe_state_inst->p++; 
  _spec_print_msg(x);
}

void _spec_probe0(iokvs_message* x) {
 
        if(_spec_probe_state_inst->p >= 1010) { printf("Error: probe more than available entries.\n"); exit(-1); }
        _spec_probe_state_inst->data[_spec_probe_state_inst->p] = x;
        _spec_probe_state_inst->p++; 
  _spec_print_msg(x);
}

void _spec_prepare_get_response(iokvs_message* p, item* it) {

iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4 + it->vallen);
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
m->mcr.request.magic = p->mcr.request.magic;
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 4;
m->mcr.request.bodylen = 4;
*((uint32_t *)m->payload) = 0;
if (it != NULL) {
  m->mcr.request.bodylen = 4 + it->vallen;
  rte_memcpy(m->payload + 4, item_value(it), it->vallen);
}


  _spec_probe0(m);
}

void _impl_unpack_set(cqe_send_setresponse* _x1) {
  
cqe_send_setresponse* entry = (cqe_send_setresponse*) _x1; 
  _impl_msg_get_set(entry->opaque);
  _impl_memcached__tx_queue_dequeue_release((q_entry*) entry);
}

void _impl_filter_full_out_fork4_inst(uint64_t _arg0) {
  __impl_fill_eqe_full_join_buffer *_p__impl_fill_eqe_full = malloc(sizeof(__impl_fill_eqe_full_join_buffer));
 
  _impl_len_core_set(_p__impl_fill_eqe_full,_arg0);
  __impl_fill_eqe_full_join_buffer_in_segment_save(_p__impl_fill_eqe_full, _arg0);  _impl_fill_eqe_full(_p__impl_fill_eqe_full->in_entry_arg0, _p__impl_fill_eqe_full->in_segment_arg0);

}

void _impl_msg_get_get(__impl_prepare_get_response_join_buffer* _p__impl_prepare_get_response, uint64_t index) {

              uint32_t key = index % 256;
              iokvs_message* val = _impl__table_msg_put_creator->data[key];
              if(val == NULL) { printf("No such entry in _impl__table_msg_put_creator table. Key = %d\n", key); exit(-1); }
              _impl__table_msg_put_creator->data[key] = NULL;
              
  __impl_prepare_get_response_join_buffer_in_packet_save(_p__impl_prepare_get_response, val);
}

void _impl_inject_inst0() {
  
        if(_impl_inject_state_inst->p >= 1000) { printf("Error: inject more than available entries.\n"); exit(-1); }
        int temp = _impl_inject_state_inst->p;
        _impl_inject_state_inst->p++;
  _impl_inject_inst0_out_fork5_inst(_impl_inject_state_inst->data[temp]);
}

void _impl_memcached__tx_queue_enqueue_submit(q_entry* eqe) {

           enqueue_submit(eqe);
           
}

void _impl_len_set(__impl_memcached_enq_alloc_set_join_buffer* _p__impl_memcached_enq_alloc_set, __impl_fill_eqe_set_join_buffer* _p__impl_fill_eqe_set, iokvs_message* m,  void* key,  size_t keylen,  uint32_t hash) {

size_t len = sizeof(eqe_rx_set);

  __impl_memcached_enq_alloc_set_join_buffer_in_len_save(_p__impl_memcached_enq_alloc_set, len);
}

void _impl_classifier(iokvs_message* m, void* key,  size_t len,  uint32_t hash) {

printf("receive id: %d\n", m->mcr.request.magic);
uint8_t cmd = m->mcr.request.opcode;


  if( (cmd == PROTOCOL_BINARY_CMD_GET)) { _impl_classifier_out_get_fork6_inst(m, key, len, hash); }
  else if( (cmd == PROTOCOL_BINARY_CMD_SET)) { _impl_classifier_out_set_fork2_inst(m, key, len, hash); }
}

void _impl_memcached_enq_alloc_set(__impl_fill_eqe_set_join_buffer* _p__impl_fill_eqe_set, size_t len, size_t c) {

           circular_queue *q = _impl_memcached__rx_queue_queues_inst->cores[c];
                      q_entry* entry = (q_entry*) enqueue_alloc(q, len);
                                 
  __impl_fill_eqe_set_join_buffer_in_entry_save(_p__impl_fill_eqe_set, entry);
}

void _impl_print_msg(iokvs_message* m) {

   uint8_t *val = m->payload + 4;
   uint8_t opcode = m->mcr.request.opcode;
   if(opcode == PROTOCOL_BINARY_CMD_GET)
        printf("GET -- id: %d, len: %d, val:%d\n", m->mcr.request.magic, m->mcr.request.bodylen, val[0]);
   else if (opcode == PROTOCOL_BINARY_CMD_SET)
        printf("SET -- id: %d, len: %d\n", m->mcr.request.magic, m->mcr.request.bodylen);
   
}

void _impl_memcached__rx_queue_enqueue_submit_ele4(q_entry* eqe) {

           enqueue_submit(eqe);
           
}

void _impl_len_get(__impl_memcached_enq_alloc_get_join_buffer* _p__impl_memcached_enq_alloc_get, __impl_fill_eqe_get_join_buffer* _p__impl_fill_eqe_get, iokvs_message* m,  void* key,  size_t keylen,  uint32_t hash) {

size_t len = sizeof(eqe_rx_get) + keylen;

  __impl_memcached_enq_alloc_get_join_buffer_in_len_save(_p__impl_memcached_enq_alloc_get, len);
}

void _spec_print_msg(iokvs_message* m) {

   uint8_t *val = m->payload + 4;
   uint8_t opcode = m->mcr.request.opcode;
   if(opcode == PROTOCOL_BINARY_CMD_GET)
        printf("GET -- id: %d, len: %d, val:%d\n", m->mcr.request.magic, m->mcr.request.bodylen, val[0]);
   else if (opcode == PROTOCOL_BINARY_CMD_SET)
        printf("SET -- id: %d, len: %d\n", m->mcr.request.magic, m->mcr.request.bodylen);
   
}

void _spec_inject_inst0_out_fork0_inst(iokvs_message* _arg0) {
  __spec_classifier_join_buffer *_p__spec_classifier = malloc(sizeof(__spec_classifier_join_buffer));
 
  __spec_classifier_join_buffer_in_pkt_save(_p__spec_classifier, _arg0);
  _spec_GetKey(_p__spec_classifier,_arg0);
}

void _impl_len_core_set(__impl_fill_eqe_full_join_buffer* _p__impl_fill_eqe_full, uint64_t full) {
  __impl_memcached_enq_alloc_full_join_buffer *_p__impl_memcached_enq_alloc_full = malloc(sizeof(__impl_memcached_enq_alloc_full_join_buffer));

size_t len = sizeof(eqe_seg_full);

  __impl_memcached_enq_alloc_full_join_buffer_in_len_save(_p__impl_memcached_enq_alloc_full, len);
  __impl_memcached_enq_alloc_full_join_buffer_in_core_save(_p__impl_memcached_enq_alloc_full, 0);  _impl_memcached_enq_alloc_full(_p__impl_fill_eqe_full, _p__impl_memcached_enq_alloc_full->in_len_arg0, _p__impl_memcached_enq_alloc_full->in_core_arg0);

}

void _impl_memcached__rx_queue_dequeue_release_ele5(q_entry* eqe) {

        dequeue_release(eqe);
           
}

void _spec_get_item_spec(iokvs_message* m, void* key,  size_t keylen,  uint32_t hash) {

    size_t totlen = m->mcr.request.bodylen - m->mcr.request.extlen;

    item *it = (item *) malloc(sizeof(item) + totlen);

        it->hv = hash;
    it->vallen = totlen - keylen;
    it->keylen = keylen;
    it->refcount = 1;
    rte_memcpy(item_key(it), key, totlen);

    
  _spec_insert_item(it);
}

void _impl_add_logseg(cqe_add_logseg* e) {

    if(_impl_segments_holder2->segbase) {
        struct _segments_holder* holder = (struct _segments_holder*) malloc(sizeof(struct _segments_holder));
        holder->segbase = e->segbase;
        holder->seglen = e->seglen;
        holder->offset = 0;
        _impl_last_segment3->holder->next = holder;
        _impl_last_segment3->holder = holder;
    }
    else {
        _impl_segments_holder2->segbase = e->segbase;
        _impl_segments_holder2->seglen = e->seglen;
        _impl_segments_holder2->offset = 0;
        _impl_last_segment3->holder = _impl_segments_holder2;
    }

    int count = 1;
    segments_holder* p = _impl_segments_holder2;
    while(p->next != NULL) {
        count++;
        p = p->next;
    }
    printf("logseg count = %d\n", count);
    
  _impl_memcached__tx_queue_dequeue_release((q_entry*) e);
}

void _spec_prepare_set_response(iokvs_message* p) {

iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4);
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.magic = p->mcr.request.magic;
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;


  _spec_probe1(m);
}

void _impl_fill_eqe_set(q_entry* _x2, item* it,  uint64_t opaque) {
  
eqe_rx_set* entry = (eqe_rx_set *) _x2;
if(entry) {
    entry->flags |= EQE_TYPE_RXSET << EQE_TYPE_SHIFT;
    entry->opaque = opaque;
    entry->item = get_pointer_offset(it);
}

  if( entry) { _impl_memcached__rx_queue_enqueue_submit_ele4((q_entry*) entry); }
}

void _impl_classifier_out_get_fork6_inst(iokvs_message* _arg0, void* _arg1, size_t _arg2, uint32_t _arg3) {
  __impl_memcached_enq_alloc_get_join_buffer *_p__impl_memcached_enq_alloc_get = malloc(sizeof(__impl_memcached_enq_alloc_get_join_buffer));
  __impl_fill_eqe_get_join_buffer *_p__impl_fill_eqe_get = malloc(sizeof(__impl_fill_eqe_get_join_buffer));
 
  _impl_len_get(_p__impl_memcached_enq_alloc_get,_p__impl_fill_eqe_get,_arg0,_arg1,_arg2,_arg3);
  _impl_get_core_get(_p__impl_memcached_enq_alloc_get,_p__impl_fill_eqe_get,_arg0,_arg1,_arg2,_arg3);
  __impl_fill_eqe_get_join_buffer_in_pkt_hash_save(_p__impl_fill_eqe_get, _arg0,_arg1,_arg2,_arg3);  _impl_fill_eqe_get(_p__impl_fill_eqe_get->in_entry_arg0, _p__impl_fill_eqe_get->in_pkt_hash_arg0, _p__impl_fill_eqe_get->in_pkt_hash_arg1, _p__impl_fill_eqe_get->in_pkt_hash_arg2, _p__impl_fill_eqe_get->in_pkt_hash_arg3);

}

void _spec_classifier(iokvs_message* m, void* key,  size_t len,  uint32_t hash) {

printf("receive id: %d\n", m->mcr.request.magic);
uint8_t cmd = m->mcr.request.opcode;


  if( (cmd == PROTOCOL_BINARY_CMD_GET)) { _spec_extract_pkt_hash0(m, key, len, hash); }
  else if( (cmd == PROTOCOL_BINARY_CMD_SET)) { _spec_extract_pkt_hash1(m, key, len, hash); }
}

void _impl_msg_put(uint64_t index, iokvs_message* val) {

              uint32_t key = index % 256;
              if(_impl__table_msg_put_creator->data[key] == NULL) _impl__table_msg_put_creator->data[key] = val;
              else { printf("Hash collision! Key = %d\n", key); exit(-1); }
              
}

void _spec_extract_pkt_hash1_out_pkt_fork1_inst(__spec_get_item_spec_join_buffer* _p__spec_get_item_spec, iokvs_message* _arg0) {
 
  __spec_get_item_spec_join_buffer_in_pkt_save(_p__spec_get_item_spec, _arg0);
  _spec_prepare_set_response(_arg0);
}

void _impl_len_cqe(__impl_fill_cqe_join_buffer* _p__impl_fill_cqe, __impl_memcached__tx_queue_enqueue_alloc_join_buffer* _p__impl_memcached__tx_queue_enqueue_alloc, uint8_t t) {

size_t len = 0;
switch(t) {
    case CQE_TYPE_GRESP: len = sizeof(cqe_send_getresponse); break;
    case CQE_TYPE_SRESP: len = sizeof(cqe_send_setresponse); break;
    case CQE_TYPE_LOG: len = sizeof(cqe_add_logseg); break;
}

  __impl_memcached__tx_queue_enqueue_alloc_join_buffer_in_len_save(_p__impl_memcached__tx_queue_enqueue_alloc, len);  _impl_memcached__tx_queue_enqueue_alloc(_p__impl_fill_cqe, _p__impl_memcached__tx_queue_enqueue_alloc->in_core_arg0, _p__impl_memcached__tx_queue_enqueue_alloc->in_len_arg0);

}

void _impl_get_core_get(__impl_memcached_enq_alloc_get_join_buffer* _p__impl_memcached_enq_alloc_get, __impl_fill_eqe_get_join_buffer* _p__impl_fill_eqe_get, iokvs_message* m,  void* key,  size_t keylen,  uint32_t hash) {

    
  __impl_memcached_enq_alloc_get_join_buffer_in_core_save(_p__impl_memcached_enq_alloc_get, hash % 4);  _impl_memcached_enq_alloc_get(_p__impl_fill_eqe_get, _p__impl_memcached_enq_alloc_get->in_len_arg0, _p__impl_memcached_enq_alloc_get->in_core_arg0);

}

void _spec_GetKey(__spec_classifier_join_buffer* _p__spec_classifier, iokvs_message* m) {

void *key = m->payload + m->mcr.request.extlen;
size_t len = m->mcr.request.keylen;

  _spec_Jenkins_Hash(_p__spec_classifier,key, len);
}

void _impl_fill_eqe_get(q_entry* _x3, iokvs_message* m,  void* key,  size_t keylen,  uint32_t hash) {

eqe_rx_get* entry = (eqe_rx_get *) _x3;
if(entry) {
    entry->flags |= EQE_TYPE_RXGET << EQE_TYPE_SHIFT;
    entry->opaque = m->mcr.request.magic;
    entry->hash = hash;
    entry->keylen = keylen;
        rte_memcpy(entry->key, key, keylen);
}

  if( entry) { _impl_memcached__rx_queue_enqueue_submit_ele4((q_entry*) entry); }
}

void _impl_filter_full(uint64_t full) {


  if( full) { _impl_filter_full_out_fork4_inst(full); }
}

void _spec_Lookup(__spec_prepare_get_response_join_buffer* _p__spec_prepare_get_response, void* key,  size_t length,  uint32_t hash) {

item *it = hasht_get(key, length, hash);

  __spec_prepare_get_response_join_buffer_in_item_save(_p__spec_prepare_get_response, it);  _spec_prepare_get_response(_p__spec_prepare_get_response->in_packet_arg0, _p__spec_prepare_get_response->in_item_arg0);

}

void _impl_prepare_set_response(iokvs_message* p) {

iokvs_message *m = (iokvs_message *) malloc(sizeof(iokvs_message) + 4);
m->mcr.request.opcode = PROTOCOL_BINARY_CMD_SET;
m->mcr.request.magic = p->mcr.request.magic;
m->mcr.request.keylen = 0;
m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
m->mcr.request.status = 0;

m->mcr.request.extlen = 0;
m->mcr.request.bodylen = 0;


  _impl_probe1(m);
}

void _impl_unpack_get(cqe_send_getresponse* _x4) {
  __impl_prepare_get_response_join_buffer *_p__impl_prepare_get_response = malloc(sizeof(__impl_prepare_get_response_join_buffer));
  
cqe_send_getresponse* entry = (cqe_send_getresponse*) _x4; 
  _impl_msg_get_get(_p__impl_prepare_get_response,entry->opaque);
  __impl_prepare_get_response_join_buffer_in_item_save(_p__impl_prepare_get_response, get_pointer(entry->item));  _impl_prepare_get_response(_p__impl_prepare_get_response->in_packet_arg0, _p__impl_prepare_get_response->in_item_arg0);

  _impl_memcached__tx_queue_dequeue_release((q_entry*) entry);
}

void _impl_fill_cqe(q_entry* e, uint8_t t, uint64_t base, uint64_t size, uint64_t opaque) {

if(e) {
        e->flags |= (uint16_t) t << CQE_TYPE_SHIFT;
    
    if(t == CQE_TYPE_GRESP) {
        cqe_send_getresponse* es = (cqe_send_getresponse*) e;
        es->opaque = opaque;
        es->item = base;
    }
    else if(t == CQE_TYPE_SRESP) {
        cqe_send_setresponse* es = (cqe_send_setresponse*) e;
        es->opaque = opaque;
    }
    else if(t == CQE_TYPE_LOG) {
        cqe_add_logseg* es = (cqe_add_logseg*) e;
        es->segbase = base;
        es->seglen = size;
        }
}

    
  if( e) { _impl_memcached__tx_queue_enqueue_submit(e); }
}

void _impl_get_core_set(__impl_memcached_enq_alloc_set_join_buffer* _p__impl_memcached_enq_alloc_set, __impl_fill_eqe_set_join_buffer* _p__impl_fill_eqe_set, iokvs_message* m,  void* key,  size_t keylen,  uint32_t hash) {

    
  __impl_memcached_enq_alloc_set_join_buffer_in_core_save(_p__impl_memcached_enq_alloc_set, hash % 4);  _impl_memcached_enq_alloc_set(_p__impl_fill_eqe_set, _p__impl_memcached_enq_alloc_set->in_len_arg0, _p__impl_memcached_enq_alloc_set->in_core_arg0);

}

void _impl_Jenkins_Hash(__impl_classifier_join_buffer* _p__impl_classifier, void* key,  size_t length) {

uint32_t hash = jenkins_hash(key, length);

  __impl_classifier_join_buffer_in_hash_save(_p__impl_classifier, key, length, hash);  _impl_classifier(_p__impl_classifier->in_pkt_arg0, _p__impl_classifier->in_hash_arg0, _p__impl_classifier->in_hash_arg1, _p__impl_classifier->in_hash_arg2);

}

void _impl_classifier_out_set_fork2_inst(iokvs_message* _arg0, void* _arg1, size_t _arg2, uint32_t _arg3) {
  __impl_memcached_enq_alloc_set_join_buffer *_p__impl_memcached_enq_alloc_set = malloc(sizeof(__impl_memcached_enq_alloc_set_join_buffer));
  __impl_fill_eqe_set_join_buffer *_p__impl_fill_eqe_set = malloc(sizeof(__impl_fill_eqe_set_join_buffer));
 
  _impl_len_set(_p__impl_memcached_enq_alloc_set,_p__impl_fill_eqe_set,_arg0,_arg1,_arg2,_arg3);
  _impl_get_core_set(_p__impl_memcached_enq_alloc_set,_p__impl_fill_eqe_set,_arg0,_arg1,_arg2,_arg3);
  _impl_get_item(_p__impl_fill_eqe_set,_arg0,_arg1,_arg2,_arg3);
}

void _impl_classifier_rx(q_entry* e) {

uint8_t type = CQE_TYPE_NOP;
if(e) {
    type = (e->flags & CQE_TYPE_MASK) >> CQE_TYPE_SHIFT;
}


  if( (type == CQE_TYPE_GRESP)) { _impl_unpack_get((cqe_send_getresponse*) e); }
  else if( (type == CQE_TYPE_SRESP)) { _impl_unpack_set((cqe_send_setresponse*) e); }
  else if( (type == CQE_TYPE_LOG)) { _impl_add_logseg((cqe_add_logseg*) e); }
  else if( e) { _impl_memcached__tx_queue_dequeue_release(e); }
}

void _impl_memcached__tx_queue_dequeue_release(q_entry* eqe) {

        dequeue_release(eqe);
           
}

void _impl_memcached__tx_queue_enqueue_alloc(__impl_fill_cqe_join_buffer* _p__impl_fill_cqe, size_t c, size_t len) {

           circular_queue *q = _impl_memcached__tx_queue_queues_inst->cores[c];
           q_entry* entry = (q_entry*) enqueue_alloc(q, len);
           
  __impl_fill_cqe_join_buffer_in_entry_save(_p__impl_fill_cqe, entry);
}

void _spec_extract_pkt_hash0(iokvs_message* m,  void* key,  size_t len,  uint32_t hash) {
  __spec_prepare_get_response_join_buffer *_p__spec_prepare_get_response = malloc(sizeof(__spec_prepare_get_response_join_buffer));



  __spec_prepare_get_response_join_buffer_in_packet_save(_p__spec_prepare_get_response, m);
  _spec_Lookup(_p__spec_prepare_get_response,key, len, hash);
}

void _spec_extract_pkt_hash1(iokvs_message* m,  void* key,  size_t len,  uint32_t hash) {
  __spec_get_item_spec_join_buffer *_p__spec_get_item_spec = malloc(sizeof(__spec_get_item_spec_join_buffer));



  _spec_extract_pkt_hash1_out_pkt_fork1_inst(_p__spec_get_item_spec,m);
  __spec_get_item_spec_join_buffer_in_hash_save(_p__spec_get_item_spec, key, len, hash);  _spec_get_item_spec(_p__spec_get_item_spec->in_pkt_arg0, _p__spec_get_item_spec->in_hash_arg0, _p__spec_get_item_spec->in_hash_arg1, _p__spec_get_item_spec->in_hash_arg2);

}

void _impl_GetOpaque(__impl_msg_put_join_buffer* _p__impl_msg_put, iokvs_message* m) {


  __impl_msg_put_join_buffer_in_index_save(_p__impl_msg_put, m->mcr.request.magic);
}

void _impl_msg_get_set(uint64_t index) {

              uint32_t key = index % 256;
              iokvs_message* val = _impl__table_msg_put_creator->data[key];
              if(val == NULL) { printf("No such entry in _impl__table_msg_put_creator table. Key = %d\n", key); exit(-1); }
              _impl__table_msg_put_creator->data[key] = NULL;
              
  _impl_prepare_set_response(val);
}

void _impl_memcached_identiy67_out1_fork3_inst(__impl_fill_cqe_join_buffer* _p__impl_fill_cqe, __impl_memcached__tx_queue_enqueue_alloc_join_buffer* _p__impl_memcached__tx_queue_enqueue_alloc, uint8_t _arg0) {
 
  _impl_len_cqe(_p__impl_fill_cqe,_p__impl_memcached__tx_queue_enqueue_alloc,_arg0);
  __impl_fill_cqe_join_buffer_in_type_save(_p__impl_fill_cqe, _arg0);
}

void send_cq(size_t arg0, uint8_t arg1, uint64_t arg2, uint64_t arg3, uint64_t arg4) { _impl_memcached_identiy67(arg0, arg1, arg2, arg3, arg4); }

void release(q_entry* arg0) { _impl_memcached__rx_queue_dequeue_release_ele5(arg0); }

q_entry* get_eq(size_t arg0) { return _impl_memcached__rx_queue_dequeue_get0(arg0); }

void init(char *argv[]) {
  init_memory_regions();
  init_state_instances(argv);
  for(int i = 0; i < 1000; i++) {
    iokvs_message* temp = random_request(i);
    _spec_inject_state_inst->data[i] = temp;
    _impl_inject_state_inst->data[i] = temp;
  }
}

void finalize_and_check() {
  cmp_func(_spec_probe_state_inst->p, _spec_probe_state_inst->data, _impl_probe_state_inst->p, _impl_probe_state_inst->data);
  finalize_memory_regions();
  finalize_state_instances();
}


pthread_t _thread__spec_inject_inst0;

    void *_run__spec_inject_inst0(void *threadid) {
        usleep(1000);
        for(int i=0; i<1000; i++) {
            //printf("inject = %d\n", i);
            _spec_inject_inst0();
            usleep(50);
        }
        pthread_exit(NULL);
    }pthread_t _thread__impl_inject_inst0;

    void *_run__impl_inject_inst0(void *threadid) {
        usleep(1000);
        for(int i=0; i<1000; i++) {
            //printf("inject = %d\n", i);
            _impl_inject_inst0();
            usleep(50);
        }
        pthread_exit(NULL);
    }pthread_t _thread__impl_memcached__tx_queue_dequeue_get;
void *_run__impl_memcached__tx_queue_dequeue_get(void *threadid) { while(true) { _impl_memcached__tx_queue_dequeue_get(); /* usleep(1000); */ } }
void run_threads() { }
void spec_run_threads() {
  pthread_create(&_thread__spec_inject_inst0, NULL, _run__spec_inject_inst0, NULL);
}
void impl_run_threads() {
  pthread_create(&_thread__impl_inject_inst0, NULL, _run__impl_inject_inst0, NULL);
  pthread_create(&_thread__impl_memcached__tx_queue_dequeue_get, NULL, _run__impl_memcached__tx_queue_dequeue_get, NULL);
}
void kill_threads() { }
void spec_kill_threads() {
  pthread_cancel(_thread__spec_inject_inst0);
}
void impl_kill_threads() {
  pthread_cancel(_thread__impl_inject_inst0);
  pthread_cancel(_thread__impl_memcached__tx_queue_dequeue_get);
}

