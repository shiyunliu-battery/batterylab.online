# External short circuit

- Section: Thermal
- Pages: 82-85
- Source PDF: Test methods for battery understanding_v3_0.pdf

External short circuit
[eCAIMAN, AIT (H.Popp)]
[This test item is reviewed/ further deepened by: project {eCAIMAN, SPICY, FiveVB}, institute,
people]
Test intention
Goal is to determine the behaviour of the cell subjected to an external short circuit. This is an
abusive out of operation test to investigate cell and system safety under extreme conditions.
External short circuits could happen for example in a vehicle crash or due to false maintenance
action.
Application(s)
Performed on all levels from cell to full system. As it is a very plausible fault condition it is
integrated in most standards and is interesting for all kind of vehicles as well as for transport of the
system and also stationary application.
Test approach
Normally the test is conducted on a fully charged device under test, as this is the worst case
scenario. A hard short circuit is to be established leading to very high currents. This either triggers
the internal overcurrent detection device (fuse) or causes high thermal stress in the cell.
Test equipment
The needed equipment is:
– A short circuit device which can handle currents up to 100 times the nominal current of the
device under test. Including all the cables, connectors and measurement devices like shunt
resistance. All should be generously dimensioned to minimize short circuit resistance4.
– Current measurement device with very high sampling rate which can handle up to 100
times the nominal current of the cell.
– The release of toxic gases as well as flammable gases should be measured.
Test procedure
• Adjust the SOC of cell to 100 % in accordance with 5.3.
• Adjusted cell as above shall be stored at room temperature, and be then short-circuited by
connecting the positive and negative terminals with an external resistance for 10 min. A
total external resistance shall be equal to or less than 5 mΩ as agreed between the
customer and the manufacturer.
4 Most standards require a short circuit resistance of <5mΩ. Customer requirements are often more
demanding. Short circuit resistances of <250µΩ are a practical value.
82

Test methods for improved battery cell understanding Thermal
Test duration
Test duration usually is very short. Often the short circuit has to be maintained for 1 h or 10min
plus 1h observation time.
Difference with similar methods in standards or usual practice
Test standards that comprise a capacity test are:
UN38.3: Test is conducted at 55°C, short circuit is maintained for 1h.
IEC62281: Similar to UN38.3 but with other period of observation.
IEC62133: Similar to UN38.3 but with different sample number.
IEC62660-2: Short circuit held for 10 min, then 1h observation time.
ISO12405-3: On pack level. Short circuit resistance less than 100mΩ.
SAEJ2929: Similar to UN 38.3.
SAND2005: Short circuit within 1s. Additional test where a resistance similar to the DC
resistance of the cell shall be used but at least higher than 10mΩ.
QC/T743: On module or higher. Test can be conducted with resistance of 1/10 or DC
resistance of module or less than 5mΩ. Second test where parts of the module are
subjected to short circuit. Temperature is the highest operation voltage.
UL2580: Similar to IEC62660-2 but different requirements.
DOE-INL/EXT: On system level with short circuit resistance of <=20mΩ. Additionally test with
current 15% below the rated value of the protection device.
Post-processing
Often the removed charge and the voltage after removing the short circuit are of interest.
Example
In this example a PHEV Module is short circuited. According to ISO12405-3. Internal protection is
removed.
Figure 37. Shows the module with the electrical connectors. It is mandatory to ensure good
electrical conductivity.
Figure 37. Module with electrical connection and thermal sensors before the test (Hybrid
Commercial Vehicle (HCV)).
83

Test methods for improved battery cell understanding Thermal
Figure 38 shows the short circuit equipment. It includes a 20kA current transformer and a 10kA
shunt. This dual system is for backup in case one measurement is not satisfying. Also there is the
high current automated switch on the right. Sampling rate of current and voltage was 20kHz and
10Hz on the temperature sensors. This is important as the test itself usually only lasts a few
seconds.
Figure 38: Short circuit equipment.
Figure 39 shows the measurements during the test. It can be seen that the current exceeds 3000A
in the beginning but then quickly declines. As soon as the short circuit is established the voltage
drops to a few mV. When the short circuit is removed after 10 min the voltage recovers.
Temperature wise it can be seen that there are peak temperatures close to 70°C at the spots. The
module did not vent, catch fire or explode.
84

Test methods for improved battery cell understanding Thermal
Figure 39. Results of short circuit test (HCV).
Figure 40 shows the casing after the test. It can be seen that the case melted a little during the test.
This is an indicator that the maximum temperatures at some spots were higher than on those spots
measured in Figure 39. However, this is a minor issue and the module has passed the test
requirements.
Figure 40. Case after short circuit test (HCV).
85