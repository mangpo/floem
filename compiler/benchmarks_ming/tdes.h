////////////////////////////////////////////////////////////////////////////////
//
// tdes.h - Easy Triple-DES
// Copyright (C) 2009  Mehter Tariq <mehtertariq@integramicro.com>
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
//
////////////////////////////////////////////////////////////////////////////////
#ifdef _TDES_H_
////////////////////////////////////////////////////////////////////////////////
unsigned char ip[64]={
	58, 50, 42, 34, 26, 18, 10, 2,
	60, 52, 44, 36, 28, 20, 12, 4,
	62, 54, 46, 38, 30, 22, 14, 6,
	64, 56, 48, 40, 32, 24, 16, 8,
	57, 49, 41, 33, 25, 17,  9, 1,
	59, 51, 43, 35, 27, 19, 11, 3,
	61, 53, 45, 37, 29, 21, 13, 5,
	63, 55, 47, 39, 31, 23, 15, 7
};
////////////////////////////////////////////////////////////////////////////////
unsigned char ip_inv[64]={
	40, 8, 48, 16, 56, 24, 64, 32,
	39, 7, 47, 15, 55, 23, 63, 31,
	38, 6, 46, 14, 54, 22, 62, 30,
	37, 5, 45, 13, 53, 21, 61, 29,
	36, 4, 44, 12, 52, 20, 60, 28,
	35, 3, 43, 11, 51, 19, 59, 27,
	34, 2, 42, 10, 50, 18, 58, 26,
	33, 1, 41,  9, 49, 17, 57, 25,
};
////////////////////////////////////////////////////////////////////////////////
unsigned char e[48]={
	32,  1,  2,  3,  4,  5,
	 4,  5,  6,  7,  8,  9,
	 8,  9, 10, 11, 12, 13,
	12, 13, 14, 15, 16, 17,
	16, 17, 18, 19, 20, 21,
	20, 21, 22, 23, 24, 25,
	24, 25, 26, 27, 28, 29,
	28, 29, 30, 31, 32,  1
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s1[4][16]={
	{14,  4, 13,  1,  2, 15, 11,  8,  3, 10,  6, 12,  5,  9,  0,  7},
	{ 0, 15,  7,  4, 14,  2, 13,  1, 10,  6, 12, 11,  9,  5,  3,  8},
	{ 4,  1, 14,  8, 13,  6,  2, 11, 15, 12,  9,  7,  3, 10,  5,  0},
	{15, 12,  8,  2,  4,  9,  1,  7,  5, 11,  3, 14, 10,  0,  6, 13}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s2[4][16]={
	{15,  1,  8, 14,  6, 11,  3,  4,  9,  7,  2, 13, 12,  0,  5, 10},
	{ 3, 13,  4,  7, 15,  2,  8, 14, 12,  0,  1, 10,  6,  9, 11,  5},
	{ 0, 14,  7, 11, 10,  4, 13,  1,  5,  8, 12,  6,  9,  3,  2, 15},
	{13,  8, 10,  1,  3, 15,  4,  2, 11,  6,  7, 12,  0,  5, 14,  9}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s3[4][16]={
	{10,  0,  9, 14,  6,  3, 15,  5,  1, 13, 12,  7, 11,  4,  2,  8},
	{13,  7,  0,  9,  3,  4,  6, 10,  2,  8,  5, 14, 12, 11, 15,  1},
	{13,  6,  4,  9,  8, 15,  3,  0, 11,  1,  2, 12,  5, 10, 14,  7},
	{ 1, 10, 13,  0,  6,  9,  8,  7,  4, 15, 14,  3, 11,  5,  2, 12}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s4[4][16]={
	{ 7, 13, 14,  3,  0,  6,  9, 10,  1,  2,  8,  5, 11, 12,  4, 15},
	{13,  8, 11,  5,  6, 15,  0,  3,  4,  7,  2, 12,  1, 10, 14,  9},
	{10,  6,  9,  0, 12, 11,  7, 13, 15,  1,  3, 14,  5,  2,  8,  4},
	{ 3, 15,  0,  6, 10,  1, 13,  8,  9,  4,  5, 11, 12,  7,  2, 14}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s5[4][16]={
	{ 2, 12,  4,  1,  7, 10, 11,  6,  8,  5,  3, 15, 13,  0, 14,  9},
	{14, 11,  2, 12,  4,  7, 13,  1,  5,  0, 15, 10,  3,  9,  8,  6},
	{ 4,  2,  1, 11, 10, 13,  7,  8, 15,  9, 12,  5,  6,  3,  0, 14},
	{11,  8, 12,  7,  1, 14,  2, 13,  6, 15,  0,  9, 10,  4,  5,  3}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s6[4][16]={
	{12,  1, 10, 15,  9,  2,  6,  8,  0, 13,  3,  4, 14,  7,  5, 11},
	{10, 15,  4,  2,  7, 12,  9,  5,  6,  1, 13, 14,  0, 11,  3,  8},
	{ 9, 14, 15,  5,  2,  8, 12,  3,  7,  0,  4, 10,  1, 13, 11,  6},
	{ 4,  3,  2, 12,  9,  5, 15, 10, 11, 14,  1,  7,  6,  0,  8, 13}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s7[4][16]={
	{ 4, 11,  2, 14, 15,  0,  8, 13,  3, 12,  9,  7,  5, 10,  6,  1},
	{13,  0, 11,  7,  4,  9,  1, 10, 14,  3,  5, 12,  2, 15,  8,  6},
	{ 1,  4, 11, 13, 12,  3,  7, 14, 10, 15,  6,  8,  0,  5,  9,  2},
	{ 6, 11, 13,  8,  1,  4, 10,  7,  9,  5,  0, 15, 14,  2,  3, 12}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char s8[4][16]={
	{13,  2,  8,  4,  6, 15, 11,  1, 10,  9,  3, 14,  5,  0, 12,  7},
	{ 1, 15, 13,  8, 10,  3,  7,  4, 12,  5,  6, 11,  0, 14,  9,  2},
	{ 7, 11,  4,  1,  9, 12, 14,  2,  0,  6, 10, 13, 15,  3,  5,  8},
	{ 2,  1, 14,  7,  4, 10,  8, 13, 15, 12,  9,  0,  3,  5,  6, 11}
};
////////////////////////////////////////////////////////////////////////////////
unsigned char p[32]={
	16,  7, 20, 21,
	29, 12, 28, 17,
	 1, 15, 23, 26,
	 5, 18, 31, 10,
	 2,  8, 24, 14,
	32, 27,  3,  9,
	19, 13, 30,  6,
	22, 11,  4, 25
};
////////////////////////////////////////////////////////////////////////////////
unsigned char pc1[56]={
	57, 49, 41, 33, 25, 17,  9,
	 1, 58, 50, 42, 34, 26, 18,
	10,  2, 59, 51, 43, 35, 27,
	19, 11,  3, 60, 52, 44, 36,
	
	63, 55, 47, 39, 31, 23, 15,
	 7, 62, 54, 46, 38, 30, 22,
	14,  6, 61, 53, 45, 37, 29,
	21, 13,  5, 28, 20, 12,  4
};
////////////////////////////////////////////////////////////////////////////////
unsigned char left_shifts[16]={
	1,
	1,
	2,
	2,
	2,
	2,
	2,
	2,
	1,
	2,
	2,
	2,
	2,
	2,
	2,
	1
};
////////////////////////////////////////////////////////////////////////////////
unsigned char pc2[48]={
	14, 17, 11, 24,  1,  5,
	 3, 28, 15,  6, 21, 10,
	23, 19, 12,  4, 26,  8,
	16,  7, 27, 20, 13,  2,
	41, 52, 31, 37, 47, 55,
	30, 40, 51, 45, 33, 48,
	44, 49, 39, 56, 34, 53,
	46, 42, 50, 36, 29, 32
};
////////////////////////////////////////////////////////////////////////////////
unsigned char row; // global variable
unsigned char col; // global variable
unsigned char s_element; // global variable
unsigned char temp; // global variable
unsigned char perm_input[64]; // global variable
unsigned char pre_output[64]; // global variable
unsigned char k[3][16][48]; // global variable
unsigned char l[32]; // global variable
unsigned char r[32]; // global variable
unsigned char b[48]; // global variable
unsigned char s[32]; // global variable
unsigned char f[32]; // global variable
unsigned char c[28]; // global variable
unsigned char d[28]; // global variable
unsigned char cd[56]; // global variable
////////////////////////////////////////////////////////////////////////////////
void left_shift(int n, unsigned char *arr);
void print(unsigned char arr[]);
void tdes_init(unsigned char key_ring[3][8]);
void des_encrypt(int stage);
void des_decrypt(int stage);
void tdes_encrypt(unsigned long n, unsigned char *in, unsigned char *out);
void tdes_decrypt(unsigned long n, unsigned char *in, unsigned char *out);
////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////                      
//                                                                                                    
// Key: Key1, Key2, Key3                                                                              
// Key1: 01 01 01 01 01 01 01 01 (odd parity set)                                                     
// Key2: 01 01 01 01 01 01 01 01 (odd parity set)                                                     
// Key3: 01 01 01 01 01 01 01 01 (odd parity set)                                                     
//                                                                                                    
////////////////////////////////////////////////////////////////////////////////                      
unsigned char key[3][64]={
  {
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1
  },
  {
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1
  },
  {
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 1
  }
};
////////////////////////////////////////////////////////////////////////////////                      
//                                                                                                    
// Plain Text: 80 00 00 00 00 00 00 00                                                                
//                                                                                                    
////////////////////////////////////////////////////////////////////////////////                      
unsigned char pt[64]={
  1, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
};
////////////////////////////////////////////////////////////////////////////////                      
//                                                                                                    
// Cipher Text: 95 F8 A5 E5 DD 31 D9 00                                                               
//                                                                                                    
////////////////////////////////////////////////////////////////////////////////                      
unsigned char et[64];
//////////////////////////////////////////////////////////////////////////////// 
#else
////////////////////////////////////////////////////////////////////////////////                      
extern unsigned char key[3][64];
extern unsigned char pt[64];
extern unsigned char et[64];
////////////////////////////////////////////////////////////////////////////////  
extern unsigned char ip[64];
extern unsigned char ip_inv[64];
extern unsigned char e[48];
extern unsigned char s1[4][16];
extern unsigned char s2[4][16];
extern unsigned char s3[4][16];
extern unsigned char s4[4][16];
extern unsigned char s5[4][16];
extern unsigned char s6[4][16];
extern unsigned char s7[4][16];
extern unsigned char s8[4][16];
extern unsigned char p[32];
extern unsigned char pc1[56];
extern unsigned char left_shifts[16];
extern unsigned char pc2[48];
////////////////////////////////////////////////////////////////////////////////
extern unsigned char row; // global variable
extern unsigned char col; // global variable
extern unsigned char s_element; // global variable
extern unsigned char temp; // global variable
extern unsigned char perm_input[64]; // global variable
extern unsigned char pre_output[64]; // global variable
extern unsigned char k[3][16][48]; // global variable
extern unsigned char l[32]; // global variable
extern unsigned char r[32]; // global variable
extern unsigned char b[48]; // global variable
extern unsigned char s[32]; // global variable
extern unsigned char f[32]; // global variable
extern unsigned char c[28]; // global variable
extern unsigned char d[28]; // global variable
extern unsigned char cd[56]; // global variable
////////////////////////////////////////////////////////////////////////////////
extern void left_shift(int n, unsigned char *arr);
extern void print(unsigned char arr[]);
extern void tdes_init(unsigned char key_ring[3][8]);
extern void des_encrypt(int stage);
extern void des_decrypt(int stage);
extern void tdes_encrypt(unsigned long n, unsigned char *in, unsigned char *out);
extern void tdes_decrypt(unsigned long n, unsigned char *in, unsigned char *out);
////////////////////////////////////////////////////////////////////////////////
#endif
////////////////////////////////////////////////////////////////////////////////
