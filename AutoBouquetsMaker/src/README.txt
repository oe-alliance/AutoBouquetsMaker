Contents:

1) CustomMix or CustomLCN?
2) CustomLCN
3) CustomMix
4) Favourites
5) Hacks
6) Streams
7) Provider keys
8) Make your own provider files
9) lamedb format explained
10) swapchannels (in providers.xml)
11) Freesat, special config for people outside the footprint of the home transponder.
12) DVB-T frequency finder

----------------------------------------------------------------------------------------------

CustomMix or CustomLCN?
-----------------------

What is the difference between CustomMix and CustomLCN?

CustomLCN is for allocating LCNs (logical channel numbers) to channels that don't have them.
It should be considered a system file and not be used to move channels around that already
have LCNs allocated to them. Once a channel has an LCN allocated this is persistent for the
entire duration of the current ABM run. So that channel can later be used in a CustomMix file
refered to by the allocated LCN.

CustomMix on the other hand, is for moving channels around, either within one provider or
from one provider to another. It only affects what is written in the bouquets of the current
provider and is not persistent. i.e.. if you move a channel in one provider from say 101 to
105 you would still use its original number if accessing it from a CustomMix file of another
provider.

So to sum up, only use a CustomLCN file for allocating LCNs. For everything else use CustomMix.

----------------------------------------------------------------------------------------------

CustomLCN
---------

CustomLCN allows channels to be moved around within one single provider. CustomLCN is
for providers that don't transmit logical channel numbers (e.g. Sky DE). Its purpose is
to insert logical channel numbers. The CustomLCN list can be complete or partial.
It doesn't have to be in any particular order but having it sequential will make it
easier to avoid making errors.

Each time ABM runs it makes an example CustomLCN xml file for each provider that is scanned,
e.g. 'EXAMPLE_hd_sat_freesat_CustomLCN.xml'. These files are archived in:
/etc/enigma2/AutoBouquetsMaker/custom
To make your own custom LCN file just delete 'EXAMPLE_' from the filename,
i.e. hd_sat_freesat_CustomLCN.xml. Configurations in the provider xml file, such as channel swap,
etc, are done after CustomLCN has been processed.

The following is how to edit the file. Just cut and paste the lines into the order you want.
DO NOT add any channels into more than one place in the list.

Also don't forget to include the ABM custom folder in your backups otherwise your newly
created file may be lost during image updates.

This is an example of the original 'EXAMPLE_" file:
<custom>
	<include>yes</include>
	<lcnlist>
		<configuration lcn="101" channelnumber="101" description="BBC One Lon"></configuration>
		<configuration lcn="102" channelnumber="102" description="BBC Two HD"></configuration>
		<configuration lcn="103" channelnumber="103" description="ITV"></configuration>
		<configuration lcn="104" channelnumber="104" description="Channel 4"></configuration>
		<configuration lcn="105" channelnumber="105" description="Channel 5"></configuration>
		<configuration lcn="106" channelnumber="106" description="BBC Three HD"></configuration>
		<configuration lcn="107" channelnumber="107" description="BBC Four HD"></configuration>
		<configuration lcn="108" channelnumber="108" description="BBC One HD"></configuration>
		<configuration lcn="109" channelnumber="109" description="BBC Two Eng"></configuration>
		<configuration lcn="110" channelnumber="110" description="BBC ALBA"></configuration>

This is how to swap channels.
If you want to swap ITV (103) with BBC Three HD (106) cut and paste both lines.
<custom>
	<include>yes</include>
	<lcnlist>
		<configuration lcn="101" channelnumber="101" description="BBC One Lon"></configuration>
		<configuration lcn="102" channelnumber="102" description="BBC Two HD"></configuration>
		<configuration lcn="106" channelnumber="106" description="BBC Three HD"></configuration>
		<configuration lcn="104" channelnumber="104" description="Channel 4"></configuration>
		<configuration lcn="105" channelnumber="105" description="Channel 5"></configuration>
		<configuration lcn="103" channelnumber="103" description="ITV"></configuration>
		<configuration lcn="107" channelnumber="107" description="BBC Four HD"></configuration>
		<configuration lcn="108" channelnumber="108" description="BBC One HD"></configuration>
		<configuration lcn="109" channelnumber="109" description="BBC Two Eng"></configuration>
		<configuration lcn="110" channelnumber="110" description="BBC ALBA"></configuration>

Now change the lcn numbers. lcn numbers should be in order to avoid errors!!
<custom>
	<include>yes</include>
	<lcnlist>
		<configuration lcn="101" channelnumber="101" description="BBC One Lon"></configuration>
		<configuration lcn="102" channelnumber="102" description="BBC Two HD"></configuration>
		<configuration lcn="103" channelnumber="106" description="BBC Three HD"></configuration>
		<configuration lcn="104" channelnumber="104" description="Channel 4"></configuration>
		<configuration lcn="105" channelnumber="105" description="Channel 5"></configuration>
		<configuration lcn="106" channelnumber="103" description="ITV"></configuration>
		<configuration lcn="107" channelnumber="107" description="BBC Four HD"></configuration>
		<configuration lcn="108" channelnumber="108" description="BBC One HD"></configuration>
		<configuration lcn="109" channelnumber="109" description="BBC Two Eng"></configuration>
		<configuration lcn="110" channelnumber="110" description="BBC ALBA"></configuration>

Removing channels.
Channel removal only applies to unsorted lists, i.e. non-LCN providers where the list has not been
sorted in any way. To remove a channel, just delete the line. NOTE: When <include>is set to 'yes',
all channels not configured in the custom xml will be added at the end of the main bouquet. This way
also new services from the provider will be added at the end of the channel list. Any new channels
will be shown in the ABM log.

Changing 'channel numbers'.
If you want your own numbering, edit the lcn numbers. lcn numbers should be in order to avoid errors!!
<custom>
	<include>no</include>
	<lcnlist>
		<configuration lcn="1" channelnumber="101" description="BBC One Lon"></configuration>
		<configuration lcn="2" channelnumber="102" description="BBC Two HD"></configuration>
		<configuration lcn="3" channelnumber="103" description="ITV"></configuration>
		<configuration lcn="4" channelnumber="104" description="Channel 4"></configuration>
		<configuration lcn="5" channelnumber="105" description="Channel 5"></configuration>
		<configuration lcn="6" channelnumber="106" description="BBC Three HD"></configuration>
		<configuration lcn="7" channelnumber="107" description="BBC Four HD"></configuration>
		<configuration lcn="8" channelnumber="108" description="BBC One HD"></configuration>
		<configuration lcn="9" channelnumber="109" description="BBC Two Eng"></configuration>
		<configuration lcn="10" channelnumber="110" description="BBC ALBA"></configuration>

NOTE: Be aware of correct sections in the provider xml.
e.g.
	<sections>
		<section number="101">Entertainment</section>
		<section number="200">News and Sport</section>
		<section number="300">Movies</section>
		<section number="400">Lifestyle</section>
		<section number="500">Music</section>
		<section number="600">Children</section>
		<section number="650">Special Interest</section>
		<section number="800">Shopping</section>
		<section number="870">Adult</section>
		<section number="950">Regional</section>
	</sections>

Your lcn numbering should match sections. In this example you can add a custom section.
	<sections>
		<section number="1">Custom list</section>
		<section number="101">Entertainment</section>
		<section number="200">News and Sport</section>
		<section number="300">Movies</section>
		<section number="400">Lifestyle</section>
		<section number="500">Music</section>
		<section number="600">Children</section>
		<section number="650">Special Interest</section>
		<section number="800">Shopping</section>
		<section number="870">Adult</section>
		<section number="950">Regional</section>
	</sections>

----------------------------------------------------------------------------------------------

CustomMix
---------

CustomMiX allows TV channels from one provider to be added to the bouquets of another provider.
This is great if you mainly use one provider but want to add a few channels from other providers
but don't want to create a complete list for the other provider. All providers that you want to
receive channels from must be included in every ABM scan but if you don't want complete bouquets
from that provider just set all the bouquet creation options to no.

CustomMix can also be used to move channels around interanally within one single provider.

For each provider you wish to add channels to, you need to add an xml configuration file. The xml
configuration files reside in /etc/enigma2/AutoBouquetsMaker/custom
and filenames are made up as follows... "provider_key_CustomMix.xml", e.g. for Sky UK the filename
would be "sat_282_sky_uk_CustomMix.xml". For other providers please consult the list of provider
keys below.

This is an example xml configuration file for Sky UK. Filename as above.

<custommix>
	<inserts>
		<insert provider="cable_uk_virgin" source="150" target="171"></insert> <!-- channel5 hd -->
		<insert provider="cable_uk_virgin" source="110" target="106"></insert> <!-- sky one hd -->
	</inserts>
	<deletes>
		<delete target="170"></delete> <!-- Sky 3D -->
	</deletes>
</custommix>

The "insert" lines are what do the work but all the tags must be present.
The "insert" line has 3 attributes, "provider", "source", and "target".

"provider" is the key of provider from which the channel is being imported. See below for a list of provider keys.
"source" is the channel number being imported.
"target" is the slot in the Sky UK bouquet into which that channel will be inserted.

Each channel that is to be moved requires an "insert" line.

"Delete" lines allow you to remove individual channels from the provider you are customising. Just
set "target" to the number of the channel you want to remove and it will disappear on the next scan.

----------------------------------------------------------------------------------------------

Favourites
----------

Favourites allows the creation of a complete favourites list that will preceed all other ABM bouquets.
Please note, favourites lists are static. ABM will keep your favourites list up to date if there are
changes to service references and transponder parameters but obviously it is not going to be updated
if new channels start broadcasting, so any new channels you want in the list must be added manually.

Channels selected for the favourites list can come from any providers that are being scanned, and these
providers must be scanned on every ABM run. The filename of the configuration file is "favourites.xml"
It must be placed in: /etc/enigma2/AutoBouquetsMaker/custom/

Here is an example favourites.xml file.

<favourites>
	<name>My List</name>
	<sections>
		<section number="100">Entertainment</section>
		<section number="200">Movies</section>
		<section number="300">Music</section>
		<section number="400">Sports</section>
		<section number="500">News</section>
		<section number="600">Documentaries</section>
		<section number="700">Kids</section>
		<section number="800">Other</section>
	</sections>
	<inserts>
		<insert provider="sat_282_sky_uk" source="105" target="105"></insert> <!-- channel5 hd -->
		<insert provider="sat_282_sky_uk" source="106" target="206"></insert> <!-- sky one hd -->
	</inserts>
	<bouquets>
		<main>1</main> <!-- 0 or 1 -->
		<sections>1</sections> <!-- 0 or 1 -->
	</bouquets>
</favourites>

"name" is the prefix of you favourites bouquets if you have "prefix" enabled in the ABM menu. "sections"
is used for writing the section markers to your bouquets. You must have at least one section, and only
channels with a greater channel number than the first section number will be added to your favourites
bouquets. The "insert" lines have 3 attributes, "provider", "source", and "target". "provider" is the
key of provider from which the channel is being imported. See below for a list of provider keys. "source"
is the channel number being imported. And "target" is the slot in the favourites into which that channel
will be inserted. Each channel that is to be moved requires an "insert" line.

"bouquets" -> "main" has a value of 0 or 1. "0" means no main bouquet will be created and "1" that one
will. Same for "bouquets" -> "sections". If "bouquets" -> "sections" is enabled the favourites list will
be divided up into sections bouquets as per the section numbers above.

All tags in the above example are necessary to get this working.

By default the favourites bouquet preceeds all other ABM bouquets, but it is also possible to place it after
another provider. Use a placement tag to do this and just add the number of the provider you want it to follow.

<favourites>
	<!-- default fields go here as in above example -->
	<placement>2</placement>
</favourites>




----------------------------------------------------------------------------------------------

Hacks
-----

"Hacks" is available in "Favourites" and "CustomMix". "Hacks" allows Python code to be use to
modify the channel list and sections markers, sort channels by name, make a "+1" bouquet, etc, etc,
and that this can be done dynamically rather than just creating static lists. With "Hacks" the sky
really is the limit in what bouquets can be created by ABM. Here's how "Hacks" looks in a CustomMix
file.

<custommix>
	<hacks>
<![CDATA[

# Python code here

]]>
	</hacks>
</custommix>

"Hacks" is provided for those with the ability to use it and there will only be basic support
for this feature.

----------------------------------------------------------------------------------------------

Streams
-------

"Streams" is available in "CustomMix". Sometimes a channel may not be available to you, e.g. you might be
outside the satellite footprint, but you can access it via a stream. In these cases use a "stream" tag.

"url" may be an encoded or non encoded url.
"target" is the number of the channel you wish to attach the url stream to.
"name" is the name to be used for the stream service. (Only used when adding to empty LCN slots).

To replace a DVB service, the layout would be as below.
The name and service reference will be the same as the DVB service. This will allow EPG data and picons to also work for the stream.

<custommix>
	<streams>
		<stream url="http://stream.source:port/live/username/F36/password/308.ts" target="118" />
	</streams>
</custommix>


You can also give your stream a "service reference type". This allows you to tell the receiver which playback software to use for that individual stream.

In this example "servicereftype" has been added:

<custommix>
	<streams>
		<stream url="http://stream.source:port/live/username/F36/password/308.ts" target="118" servicereftype="4097" />
	</streams>
</custommix>

The following is a list of currently valid "service reference types":
	1		processed by the SoC (for when buffering is not required)
	4097	processed by gstreamer via servicemp3
	5001	processed by gstreamer via gst-player
	5002	processed via extplayer3

You can also add streams into empty LCN slots. As these do not have a name from the DVB source, it has to be specified.
When inserting streams into empty LCN slots, the service reference will be "1:0:1:0:0:0:0:0:0:0:".
EPG will not work becuase of this.

In this example we have added a section/bouquet too.

<custommix>
    <sections>
        <section number="700">IPTV</section>
    </sections>

    <streams>
        <stream url="http://stream.source:port/live/username/F36/password/308.ts" target="701" name="our name 1" />
        <stream url="http://stream.source:port/live/username/F36/password/309.ts" target="702" name="our name 2" />
    </streams>
</custommix>

----------------------------------------------------------------------------------------------

Provider keys
-------------

Provider name: HD Austria
Provider key: sat_235_austriasat

Provider name: HD Austria
Provider key: sat_192_austriasat

Provider name: AustriaSat 9E
Provider key: sat_90_austriasat

Provider name: Bis TV 13E
Provider key: sat_0130_bistv

Provider name: Canal Digitaal HD
Provider key: sat_192_canaldigitaal_hd

Provider name: Canal Digitaal SD
Provider key: sat_192_canaldigitaal_sd

Provider name: Canal Digitaal HD
Provider key: sat_235_canaldigitaal_hd

Provider name: Canal Digitaal SD
Provider key: sat_235_canaldigitaal_sd

Provider name: Canal+ Esp
Provider key: sat_192_canal_plus_esp

Provider name: Com Hem
Provider key: cable_swe

Provider name: FranSat
Provider key: sat_3550_fransat

Provider name: FreeSat UK
Provider key: sat_282_freesat

Provider name: FreeView (UK)
Provider key: terrestrial_uk_freeview

Provider name: HD+ (DE)
Provider key: sat_0192_hd+

Provider name: Kabel (NL)
Provider key: cable_nl

Provider name: NL Terrestrial
Provider key: terrestrial_NL_bouquet1

Provider name: Saorsat
Provider key: sat_0090_saorsat

Provider name: Saorview (IE)
Provider key: terrestrial_ie_saorview_PSB1

Provider name: Sky Deutschland
Provider key: sat_192_sky_deutschland

Provider name: Sky Italia
Provider key: sat_130_sky_italy

Provider name: Sky ROI
Provider key: sat_282_sky_irl

Provider name: Sky UK
Provider key: sat_282_sky_uk

Provider name: Skylink Czech Republic
Provider key: sat_235_skylink_czech_republic

Provider name: Skylink Slovak Republic
Provider key: sat_235_skylink_slovak_republic

Provider name: TéléSAT
Provider key: sat_192_telesat

Provider name: TeleSAT
Provider key: sat_235_telesat

Provider name: Tivusat
Provider key: sat_130_tivusat

Provider name: TNTSat
Provider key: sat_192_tntsat

Provider name: Turksat
Provider key: sat_420_turksat

Provider name: TV Vlaanderen
Provider key: sat_192_tvvlaanderen

Provider name: TV Vlaanderen
Provider key: sat_235_tvvlaanderen

Provider name: Viasat
Provider key: sat_0048_viasat.xml

Provider name: Virgin IE
Provider key: cable_ie_mk2

Provider name: Virgin (UK)
Provider key: cable_uk_virgin

----------------------------------------------------------------------------------------------
Available transponder (Satellite) parameters in provider files:

polarization
------------

| 0 | H |
| 1 | V |
| 2 | L |
| 3 | R |

fec_inner
---------

| 0 | Auto |
| 1 | 1/2  |
| 2 | 2/3  |
| 3 | 3/4  |
| 4 | 5/6  |
| 5 | 7/8  |
| 6 | 8/9  |
| 7 | 3/5  |
| 8 | 4/5  |
| 9 | 9/10 |

system
------

| 0 | DVB-S  |
| 1 | DVB-S2 |

modulation
----------

| 1 | QPSK |
| 2 | 8PSK |

----------------------------------------------------------------------------------------------

Make your own provider files
----------------------------

You can make your own providers files or modify existing ones. Place these in /etc/enigma2/AutoBouquetsMaker/providers.
These will take priority over the ones shipped with the plugin and as they are in /etc/enigma2 they should be 
automatically included in settings backups.

----------------------------------------------------------------------------------------------


lamedb (v4) format explained
----------------------------

Lamedb format:
	File is basically a fixed format file where some fields contain multiple values separated by commas or colons. Lines may not exceed 256 characters.
	It contains two sections.
	Transponders started by a line transponders. Contains transponder frequencies, symbol rates, polarization and satellite position.
	Services started by a line services. Contains SSID, Card ID for channels on a particular transponder.

Header Line:
	The file starts with a line eDVB services /%d/, where %d is format version.
	eDVB services /4/

Transponders section:
	Section starts with a line transponders.
	Followed by a DVB line and transponder data line tuples. The DVB data line starts at col 0, the transponder data line immediately follows and starts with a <TAB>.
	Lines starting at col0 contains three fields encoded in hexadecimal:

		DVB namespace
		Transport stream id
		Original network id


	Lines starting with a <TAB> character and contain DVB transponder data such as frequency and symbol rate. Three types of DVB transponders can be encoded here:

		Satellite DVB
		Terestrial DVB
		Cable DVB

	Satellite lines start with <TAB>s like: s 10773250:22000000:0:2:192:2:0:1:2:0:2 fields for version 3 and 4. All fields are separated by colons, values in decimal.

		Frequency in Hertz.
		Symbol rate in bits per second.
		Polarization: 0=Horizontal, 1=Vertical, 2=Circular Left, 3=Circular right.
		Forward Error Control (FEC): 0=None , 1=Auto, 2=1/2, 3=2/3, 4=3/4 5=5/6, 6=7/8, 7=3/5, 8=4/5, 9=8/9, 10=9/10.
		Orbital Position: in degrees East: 130 is 13.0E, 192 is 19.2E. Negative values are West -123 is 12.3West.
		Inversion: 0=Auto, 1=On, 2=Off
		Flags (Only in version 4): Field is absent in version 3.
		System: 0=DVB-S 1=DVB-S2.
		Modulation: 0=Auto, 1=QPSK, 2=QAM16, 3=8PSK.
		Rolloff (Only used in DVB-S2): 0=0.35, 1=0.25, 3=0.20
		Pilot (Only used in DVB-S2): 0=Auto, 1=Off, 2=On.


	Terrestrial lines start with <TAB>t:

		frequency in Hertz.
		Bandwidth: 0=Auto, 1=8Mhz, 2=7Mhz, 3=6Mhz.
		Code rate High Pass FEC: 0=Auto, 1=1/2, 2=2/3, 3=3/4, 4=5/6, 5=7/8.
		Code rate Low Pass FEC: 0=Auto, 1=1/2, 2=2/3, 3=3/4, 4=5/6, 5=7/8.
		Modulation: 0=Auto, 1=QPSK, 2=QAM16, 3=QAM64.
		Transmission mode: 0=Auto, 1=2k, 3=8k
		Guard Interval: 0=Auto, 1=1/32, 2=1/16, 3=1/8, 4=1/4
		Hierarchy: 0=Auto, 1=None, 2=1, 3=2, 4=4
		Inversion: 0=Auto, 1=On, 2=Off.
		Flags


	Cable lines start with <TAB>c:

		Frequency in Hertz.
		Symbol rate.
		Inversion: 0=Auto, 1=On, 2=Off.
		Modulation: 0=Auto, 1=QAM16, 2=QAM32, 3=QAM64, 4=QAM128, 5=QAM256.
		Forward Error Control innert (FEC_inner): 0=None, 1=Auto, 2=1/2, 3=2/3, 4=3/4, 5=5/6, 6=7/8, 7=8/9.
		Flags


Services section:
	The section starts with the word services on a line by itself.
	Followed by a three line tuple: DVB stream data, Channel name, Provider data line.
	The DVB stream data line contains six fields:

		Service id (SSID value from stream) in Hex
		DVB namespace in Hex.
		Transport stream id in Hex
		Original network id in Hex
		Service type in Decimal: 1=TV, 2=Radio
		Service number in Decimal.


	The Channel name is on a line by itself in some character encoding (to be investigated, probably UTF-8)
	The last line contains Provider Service data. Variable number of fields, separated by commas. Fields formed like <tag>:value. For example p:Sky Digital,c:000202,c:010282,c:020242,c:030202,c:0500 01,C:0963,C:0961,C:0960.

		Provider name field. Field tag p: Name of provider.
		Cached data. Field tag [lower case] c: followed by two decimal digits and four hexadecimal digits. For example c:010282 is composed of 01 decimal cache id, 0282 hexadecimal value to cache.
		Card ID (CAID). Field tag [upper case] C: follwed by four hexadecimal digits: Card ID. For example C:0100.
		Flag data: Field tag f: followed by hexadecimal digits.

----------------------------------------------------------------------------------------------

lamedb cached PID data
----------------------

c:00xxxx = video pid
c:01xxxx = audio pid (MPEG)
c:02xxxx = Teletext pid
c:03xxxx = PCR pid
c:04xxxx = audio pid (AC3)

c:100007 + c:11xxxx = audio pid (AC3+) ???
c:100004 + c:11xxxx = audio pid (HE-AAC) ???

c:10xxxx = cached volume level ???

c:11xxxx = audio pid (AAC)

----------------------------------------------------------------------------------------------

lamedb service flags
--------------------

dxNoSDT=1,    // don't fetch SDT
dxDontshow=2, // don't show service in all services list
dxNoDVB=4,  // dont use PMT for this service ( use cached pids )
dxHoldName=8, // don't change service name if label differs in the SDT
dxNewFound=64, // show in last scanned bouquet ( until next restart )
dxIsDedicated3D=128, // 3D channel
dxIsParentalProtected=256, // service with parental protection
dxHideVBI=512, // Hide VBI line (dotted line along top of screen on some channels )
dxIsScrambledPMT=1024, // identical to dxNoDVB when used in pmt.cpp and in servicedvbstream.cpp used to record cached pids
dxCenterDVBSubs=2048, // Centre DVB subtitles
dxNoEIT=4096, // disable EIT event parsing when using EPG_IMPORT

----------------------------------------------------------------------------------------------

swapchannels (in providers.xml)
-------------------------------

swapchannels always forces the channel order in the HD bouquets, and optionally forces the
channel order main and sections bouquets. "number" is the SD channel. "with" is the HD channel.
Swap will only occur if the source channel is not HD and the target channel is HD, and both ends
of the swap exist.

Example:
<channel number="101" with="801"/> <!-- BBC One HD -->
This moves "BBC One HD" to slot 101, and BBC One London to slot 801.

There is also a "conditional" attribute.
Example:
<channel number="102" with="802" conditonal="service_hd['channel_id'] == 2075"/> <!-- BBC Two HD -->
If the statement in the conditional attribute evaluates to True the swap will occur, if not it
will fail.

It is also possible to create compound statements.
Example:
<channel number="102" with="802" conditonal="service_sd['service_name'] == 'BBC Two Eng" and service_hd['channel_id'] == 2075"/>

The following is a non-exhaustive list of variables that could be used in a conditional attribute,
although not all will be available for all providers.

service_sd['service_name']
service_sd['channel_id']
service_sd['service_id']
service_sd['transport_stream_id']
service_sd['provider_name']
service_sd['category_name']
service_sd['original_network_id']
service_sd['bouquet_id']
service_sd['bouquet_key']

service_hd['service_name']
service_hd['channel_id']
service_hd['service_id']
service_hd['transport_stream_id']
service_hd['provider_name']
service_hd['category_name']
service_hd['original_network_id']
service_hd['bouquet_id']
service_hd['bouquet_key']


----------------------------------------------------------------------------------------------

Freesat, special config for people outside the footprint of the home transponder
--------------------------------------------------------------------------------

For people that are outside the footprint of the freesat home transponder an alternative
configuration is needed. This is much slower than using the standard configuration but
at least it allows the scan to collect the relevant data, which would not be possible
otherwise.

In the Freesat provider file, in the transponder section,
delete:
    sdt_pid="0xbba"
    bat_pid="0xbba"

add:
    bat_pid="0xf01"

Convert the rest of the transponder parameters to those of a transponder known to be
available on your dish. e.g. Sky News transponder (12207 V 27500 2/3).

Basically the above just reverts this commit:
https://github.com/oe-alliance/oe-alliance-plugins/commit/7b5d72d44523d4047b51156e3f421bd456d9f131#diff-16e2769b1de3a403922eee457aba7895

----------------------------------------------------------------------------------------------

DVB-T frequency finder
----------------------

This tool enables the creation of a provider file for UK terrestrial for users that live
in areas where the data contained in the supplied system file or SI tables may be incomplete
or wrong. This will be the case if you are receiving from a repeater or when there have been
modifications to the active frequencies on your mast that the ABM developers are not yet aware
of.

To enable the tool go into the configure menu, select "Expert" mode, and then select
"Show DVB-T frequency finder".

Then in the main ABM menu select "DVB-T frequency finder". The tool automatically steps through
all known UHF TV frequencies and works out where ABM needs to look for services. This process
takes a few minutes to complete. Once it is complete the tool creates a new provider file and
advises you of the name. Now it is just a question of going into the Providers menu and de-selecting
"FreeView (UK)" and then selecting the newly created provider, and doing a scan. You only need
to run the tool one time and from then on just let ABM scan in the normal way. If at a later
stage there seams to be something wrong with the channels you are receiving, such as a block of
channels with no signal just run the tool again.

And dont forget to push the created file back to the developers on OpenViX forum along with your
location and opinion of which mast you are receiving from.


----------------------------------------------------------------------------------------------
