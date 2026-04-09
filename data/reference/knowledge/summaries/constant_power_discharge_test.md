# Constant power discharge test

- Section: Battery cell performance
- Pages: 25-27
- Source PDF: Test methods for battery understanding_v3_0.pdf

Constant power discharge test
[This test item is elaborated by: Spicy project, Mikel Arrinda]
Test intention
The Constant Power Discharge test is designed to determine battery capacity and energy during a
constant power discharge.
Application(s)
The test results (capacity and energy content) can be used directly as key data of the battery cell.
The voltage graphs and the heating behaviour can be used to verify battery models. The effect of
the temperature on the energy density can be characterised.
Test approach
The test consists on discharging charged cells at constant power values until cut-off voltage, several
times at different discharge powers, where the discharge power values are set between maximum
and minimum power rates that the cell can provide continuously. The procedure is repeated for
different ambient temperatures. The cutoff voltage, maximum and minimum currents and
temperature must also remain within the limits specified by the manufacturers.
Test equipment
In order to perform the test, the following equipment is needed:
– battery cell tester;
– temperature or climate chamber;
– temperature sensors.
Test procedure
The test described below covers a full parametrization of the power capability of the cell.
Discharge Power rates
Default power values are those required to remove 75%, 50%, 25% of battery energy in one hour
(discharge to rated capacity or termination limits) limited up to the maximum allowed discharge
rate by the manufacturer.
Temperatures
Recommended: 5, 25, 45°C.
Optional: low temperatures: 0, -10 and -20°C at discharge. For charge the lowest permitted
temperature according to the manufacturer has to be used.
The battery behaviour is very temperature depending due to the chemical reactions and the
transport phenomena inside the battery cell. Since most battery applications lie between 5 and
45°C this is the necessary range. For consumer and outdoor batteries a (sub)zero temperature
range may be needed.
Step-by-step procedure
1. For the data acquisition during the test a measurement every minute and for every 20 mV
change, every 0.05 C change and for every 0.2 K change is recommended.
2. The battery cell has to be charged as described in the standard cycle, maximally 48 h
before.
25

Test methods for improved battery cell understanding Battery cell performance
3. A rest of 60 min is applied. For the data acquisition a measurement every minute and for
every 20 mV change and for every 0.05°C change is recommended.
4. The discharge at constant power is applied until minimum allowed cell voltage. The rates to
be applied are defined above.
5. A rest of 60 min is applied.
6. The charge at constant current is applied until the maximum allowed cell voltage. The rates
to be applied are defined by the manufacturer (nominal current rate).
7. A constant voltage charge is applied at the maximum allowed voltage until the rate
prescribed in the slow discharge test.
8. A rest of 60 min is applied
9. The steps 3, 4, 5 and 6 are repeated another 2 times (the constant power discharge is
performed 3 times).
10. The test is repeated for every power rate.
The cell temperature is followed and must be within the allowed limits as prescribed by the
manufacturer.
After changing the temperature according to the above described list, two hours is waited before
starting a discharge. The equivalent holds if the battery cell has to be heated before charging is
allowed.
If the relaxation after (dis)charge is important, e.g. to find the EMF, then the rest time may be
increased or a relaxation criterion can be introduced like less change than 5 mV/h.
A heat camera can be used, especially for power rates higher than the nominal ones.
Test duration
In case only one temperature and one power rate is investigated, the duration of the entire
procedure depends mainly on the applied power rate.
𝑁𝑜𝑚𝑖𝑛𝑎𝑙 𝑃𝑜𝑤𝑒𝑟 𝑅𝑎𝑡𝑒
𝑇𝑒𝑠𝑡 𝑑𝑢𝑟𝑎𝑡𝑖𝑜𝑛 ≈ (3∙ )+3
𝑆𝑒𝑙𝑒𝑐𝑡𝑒𝑑 𝑃𝑜𝑤𝑒𝑟 𝑅𝑎𝑡𝑒
Difference with similar methods in standards or usual practice
The same kind of test procedure can be also identified in manuals and guides which are public
available and introduced by organization or committees, e.g.:
- USABC Electric Vehicle Battery Test Procedures Manual. The manual describes the Constant
Power Discharge Test, which is analogous to the procedure introduced above. In this case,
the test intention differs from the test intention explained here:
“The purpose of this testing is to perform a sequence of constant power
discharge/charge cycles that define the voltage versus power behavior of a battery as a
function of depth of discharge. This testing characterizes the ability of a battery to
provide a sustained discharge over a range of power levels representative of electric
vehicle applications. Constant power discharges are similar to constant speed vehicle
operation in their effect on a battery.”
Post-processing
Specific data deliverables include plots of voltage vs. time and current vs. time. The obtained
energy throughput and capacity throughput are health indicators of the cell.
26

Test methods for improved battery cell understanding Battery cell performance
Example
There are different examples on-line. An example is available in:
http://www.richtek.com/Design%20Support/Technical%20Document/AN024
Here the constant power discharge test is performed in order to confirm that fuel gauge can
provide accurate SOC report at different load conditions (Figure 10 and Figure 11).
Figure 10: Voltage vs time plot using 3W, 4W and 5W constant power discharging rates until
voltage <3.2v.
Figure 11: Current vs time plot using 3W, 4W and 5W constant power discharging rates until
voltage <3.2v.
Another example is available in:
https://www.ecig.eu/pavblog/blog?id=22
Here different constant power discharge rates are applied to a group of 18650 Li-ion cells (Figure
12). The capacity throughout and energy throughout are used to compare the different 18650
tested cells in terms of capacity and energy. The capacity loss after testing is also provided (Figure
13).
27