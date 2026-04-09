# Explaining and interpreting typical data sheets

- Section: Introductory topics about battery cell testing
- Pages: 12-14
- Source PDF: Test methods for battery understanding_v3_0.pdf

Explaining and interpreting typical data sheets
[Proposed by AIT (H.Popp)]
Figure 3 to Figure 5 show the sections of a typical datasheet. In this case it is from a very frequently
used cell for portable devices: a Panasonic NCR18650B3. There is no standard or no common
agreement which information a datasheet has to include. Depending on the manufacturer, the
supplier, the field of intended application, the cell and even the customer the datasheet will look
different which also makes them hard to compare. The following sections aim to help to
understand the values provided by the manufacturer. Additional understanding can be also gained
when reading the corresponding sections in this document.
General data
Figure 3 shows the general data section of the datasheet. Under “Features & Benefits” the type of
cell (in this case it is a high energy density cell), the benefits and the field of application are given.
For experienced users the composition of the cell is also of interest but not included in this case.
Some datasheets provide this information e.g. that the cell comprises a NMC cathode and a
graphite anode.
Specifications
Rated capacity: It is the minimum capacity for discharge which can be achieved. However, the time
base to derive the capacity is not given (see also the section ‘Freedom in reference
capacity’). It is only mentioned that the ambient temperature for the rated
capacity test is 20°C. Although the rated capacity for cylindrical cells is often the 5 h
capacity, the plots in Figure 5 let believe that it is about the 1 h capacity.
Nominal voltage: Mean voltage achieved during the discharge that leads to the rated capacity
(called the standard discharge).
Capacity: Again a minimum value is provided. This one is higher because of the test being
performed at 25°C. Also the typical value is given that is the expected value for this
cell type.
Charging: States the standard charge method according to the manufacturer. In this case it is
with a C/2 rate based on the typical capacity up to 4.2V with the charging time
limited to 4h. Considering an empty cell this would account for approximately 2 h
of CC charging and then 2 h of topping at 4.2V with CV charging. Note that also
other charging strategies can be possible when imposing special boundaries, like a
cut-off current. Contact the manufacturer if necessary.
Weight: In this case the maximum weight is stated. Also median weight is common.
Temperature: Values for charge, discharge and storage are given. These are the absolute
maximum (or minimum) ratings on the surface of the cell.
Energy density: Volumetric and gravimetric energy density; in this case calculated for the worst
case scenario with minimum capacity at 25°C and maximum dimensions / mass. It
is to be expected that real values will be better.
Dimensions: Technical drawing of the cell with dimensions of cell and tabs.
Other typical values which are not found in this datasheet are:
3 http://www.batteryspace.com/prod-specs/NCR18650B.pdf
12

Test methods for improved battery cell understanding Introductory topics about battery cell testing
– Internal resistance
– Peak power (charge/discharge)
– Maximum continuous and peak current (amplitude and duration of peak current)
– Voltage limits (also voltage limits for peak power possible)
– Power density (volumetric / gravimetric)
– Material thickness (important for the corresponding connector tabs that can be used in
case of resistive welding).
Figure 3: General data section in the data sheet of the Panasonic NCR18650B cell.
Charge characteristics
Figure 4 (left) shows a typical charging curve from empty to full state with the standard charging
procedure. It can be seen that the CC charging phase takes 105 min and that the new cell is
considered as fully charged at around 180 min (3h) taking a cut-off current into account (C/50). This
is different from the charge prescription in the general section. The standard charge up to 4 h can
be necessary then when the cell is aged and has higher internal resistance.
Cycle-life characteristics
Figure 4 (right) shows the cycle-life for the cell. In this case the capacity degradation is illustrated
over the cycle count. The cell is cycled with full cycles, so the DOD is 100%. In other cases also
cycle-life for smaller discharge windows, e.g. DOD 80 % or at different currents or temperature
levels can be given.
13

Test methods for improved battery cell understanding Introductory topics about battery cell testing
Figure 4: Characteristics for charging and cycle life.
Discharge characteristics
Figure 5 (left) shows the discharge characteristics for several ambient temperatures. The C-rate for
discharge is kept constant and the temperature is varied. As the electrical performance of a battery
cell is strongly dependent on its temperature this is very helpful to estimate the cell performance
at the intended operational temperature. It can be seen that at the lowest temperature level only
two third of the capacity can be extracted in CC-mode. Figure 5 (right) shows the discharge
characteristics by discharged current. The temperature is kept constant while the C-rate is varied.
Due to the internal resistance the lower voltage limit is reached earlier with higher discharge
currents meaning that less charge can be withdrawn. For more information see also Figure 8 and
the corresponding section. In some cases also additional plots can be found which e.g. give the
internal resistance or the power capability as function of the SOC.
Figure 5: Discharge characteristics.
14