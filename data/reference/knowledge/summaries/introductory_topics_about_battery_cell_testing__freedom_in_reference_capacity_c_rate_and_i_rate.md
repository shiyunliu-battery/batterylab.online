# Freedom in reference capacity: C-rate and I-rate

- Section: Introductory topics about battery cell testing
- Pages: 8-8
- Source PDF: Test methods for battery understanding_v3_0.pdf

Freedom in reference capacity: C-rate and I-rate
t
For battery tests the current is mostly expressed in a relative manner, i.e. in terms of the battery
capacity. However, the capacity is not a fixed value. It is dependent on the current profile. Mostly,
a constant current discharge is used that discharge the battery in a certain amount of hours. This is
the definition of the rated capacity C , with n being the time base. Usual rated capacities for Li-ion
n
batteries are:
– C for portable and industrial applications (IEC 61960, IEC 62620)
5
– C for BEV application (IEC 62660-1, ISO 12405-2)
3
– C for HEV application (IEC 62660-1, ISO 12405-1)
1
To prescribe the needed currents in a test, several standards do not use C-rates, what refers to the
capacity corresponding to a full discharge in exactly 1 h. However, they use I-rates, where I refers
t t
to the capacity as measured according to the time base prescribed by the standard (the n in C ). So,
n
this could be read as a C -rate. C must not be confounded with C/n, what refers to a current of 1/n
n n
of the 1 h capacity.
For good comparison of test results, the cell capacity has to be determined in the same manner for
all tested cells. If that is e.g. the 5 h discharge capacity, then the I-rate can be used. If the cells have
t
different time bases for the declared capacity or when no time-base is given in the datasheet, then
it is better to use the 1 h capacity. This can be derived from the capacity test as given in the white
paper by interpolation of the test results. Fortunately, the capacity of Li-ion cells is at room
temperature hardly depending on the current: less than 5% difference between the 5 h and 1 h
discharge, by experience. This is much less than for other battery chemistries like lead and NiMH.
This stated, it appears that some cell manufacturers are too optimistic about the cell capacity. They
declare a capacity that even cannot be reproduced by a 100 h discharge. A 10% difference between
the declared capacity and the 1 C capacity can be found for Li-ion cells in practice.
Originally, the I-rate definition is found in IEC 61434 ‘Guide to designation of current in alkaline
t
secondary cell and battery standards’. It had to solve the unit problem that exists between capacity
(Ah) and current (A). The definition adds that the C capacity is divided by 1 [h], so that the
n
resulting unit becomes [A].
The white paper uses the C-rate as basis. It can be replaced by an I-rate. Even if the time bases of
t
the cells are not equal, this should not lead to large mismatches in the current from the 10%
capacity difference given above. This can be checked by the capacity test. If the difference becomes
above 10% then the capacity test should use the 1 h capacity (calculated by interpolation) and be
repeated. This capacity has to be used for the other tests as well in that case.
This document puts an emphasis on the C capacity since it hardly depends on the growth in
25
resistance during ageing in contrast with the C capacity. So, it represents better the available
1
battery capacity. It can be obtained relatively quickly by continuing the CC discharge with a CV
discharge until a cut-off current of C/25.
8