# Penetration

- Section: Safety aspects
- Pages: 70-73
- Source PDF: Test methods for battery understanding_v3_0.pdf

Penetration
[eCAIMAN, Hartmut Popp]
Test intention
This tests aims to simulate a short circuit within the cell; a failure which could be caused by the
growth of dendrites or by the intrusion of foreign matter during a crash. It is according to
SAE J2464:2009.
70

Test methods for improved battery cell understanding Safety aspects
Application(s)
Relevant for all applications as dendrite growth can also take place for stationary applications. It is
commonly exerted on cell level, on parallel connection of cells and modules.
Test approach
The cell in most cases is charged to SOC 100%. Short circuit in the cell is forced by a conductive
steel rod.
The release of toxic gases as well as flammable gases should be measured with appropriate gas
measurement system.
Test equipment
The needed equipment is:
– Hydraulic press with adjustable speed or special nail penetration unit;
– Nail
– Temperature sensors
– Data logger for voltage and temperature.
– Gas measurement equipment
Test procedure
– Charge cell to SOC 100% with standard charge
– Wait for thermal equilibrium at room temperature
– Penetrate the DUT with a mild steel (conductive) rod. The orientation of the penetration
shall be perpendicular to the cell electrodes.
– For cell: Diameter of Rod 3mm, Rod End Type Tapered to a sharp point, Rate of Penetration
8 cm/s or greater, Minimum Depth of Penetration Through cell.
– For Module/Pack: Diameter of Rod 20mm, Rod End Type Tapered to a sharp point, Rate of
Penetration 8 cm/s or greater, Minimum Depth of Penetration Through 3 cells or 100 mm
whichever is greater.
– The DUT should be observed for a minimum of 1 h after the test with the rod remaining in
place.
Test duration
Test duration for actual test is under 1 min. Depending on the standard the cell has to be
monitored afterwards for at least 1h.
Difference with similar methods in standards or usual practice
The penetration test is described in:
SAE J2464:2009: Reference in this case (see above)
SAND 2005-3123: Same as SAEJ2464:2009.
QC/T 743-2006: Test is called “prick test” there. Speed of nail during penetration and also
the diameter of the nail are different for this test.
Post-processing
No post-processing is necessary.
71

Test methods for improved battery cell understanding Safety aspects
Example
In this example a nail penetration test is exemplarily shown on a cylindrical cell of 26650 format
and a LFP cathode combined with a graphite anode.
Figure 31 shows the cell in the test frame during the nail penetration test. The test frame in this
case is to stabilize the cell and it has a hole on the top and on the bottom to guide the nail trough
the cell. There is also dedicated equipment which is solely for the purpose of nail penetration tests
on cylindrical cells. For those no frame is needed.
Additionally it can be seen that there are 2 thermocouples in the setup. One takes the cells surface
temperature and the other on is placed close to the venting unit to detect venting and to
determine the temperature of the exhaust. Voltage measurement takes place during the test too.
Figure 31: Cylindrical cell in test-frame during nail penetration test.
Figure 32 shows the bottom of the cell. One can see that the nail went through the cell and
electrolyte is dripping off it.
72

Test methods for improved battery cell understanding Safety aspects
Figure 32: Bottom view of cylindrical cell during nail penetration test.
Figure 33 shows the measured values during the test. It can be seen that the cell voltage
immediately drops to 0 when the cell is penetrated (see value displacement). Within the first
seconds the cell heats to close to 100°C and then the temperature is decreasing. The temperature
increase on the venting is only caused by heat radiated from the cell.
In total this is a satisfying result as the cell did not vent or catch fire during this very demanding
abusive test.
It is recommended by the authors to monitor the data at least with 10Hz to have detailed
resolution for further processing and plotting. Additionally to these values also the force needed to
drive the nail through the cell can be of interest.
Figure 33. Measurements during nail penetration test.
73