UNIT_TYPES = {
    3:'System_Snapshot_Dummy',
    21:'Ball',
    22:'StereoscopicOptionsUnit',
    23:'Colossus',
    24:'TechLab',
    25:'Reactor',
    27:'InfestorTerran',
    28:'BanelingCocoon',
    29:'Baneling',
    30:'Mothership',
    31:'PointDefenseDrone',
    32:'Changeling',
    33:'ChangelingZealot',
    34:'ChangelingMarineShield',
    35:'ChangelingMarine',
    36:'ChangelingZerglingWings',
    37:'ChangelingZergling',
    39:'CommandCenter',
    40:'SupplyDepot',
    41:'Refinery',
    42:'Barracks',
    43:'EngineeringBay',
    44:'MissileTurret',
    45:'Bunker',
    46:'RefineryRich',
    47:'SensorTower',
    48:'GhostAcademy',
    49:'Factory',
    50:'Starport',
    52:'Armory',
    53:'FusionCore',
    54:'AutoTurret',
    55:'SiegeTankSieged',
    56:'SiegeTank',
    57:'VikingAssault',
    58:'VikingFighter',
    59:'CommandCenterFlying',
    60:'BarracksTechLab',
    61:'BarracksReactor',
    62:'FactoryTechLab',
    63:'FactoryReactor',
    64:'StarportTechLab',
    65:'StarportReactor',
    66:'FactoryFlying',
    67:'StarportFlying',
    68:'SCV',
    69:'BarracksFlying',
    70:'SupplyDepotLowered',
    71:'Marine',
    72:'Reaper',
    73:'Ghost',
    74:'Marauder',
    75:'Thor',
    76:'Hellion',
    77:'Medivac',
    78:'Banshee',
    79:'Raven',
    80:'Battlecruiser',
    81:'Nuke',
    82:'Nexus',
    83:'Pylon',
    84:'Assimilator',
    85:'Gateway',
    86:'Forge',
    87:'FleetBeacon',
    88:'TwilightCouncil',
    89:'PhotonCannon',
    90:'Stargate',
    91:'TemplarArchive',
    92:'DarkShrine',
    93:'RoboticsBay',
    94:'RoboticsFacility',
    95:'CyberneticsCore',
    96:'Zealot',
    97:'Stalker',
    98:'HighTemplar',
    99:'DarkTemplar',
    100:'Sentry',
    101:'Phoenix',
    102:'Carrier',
    103:'VoidRay',
    104:'WarpPrism',
    105:'Observer',
    106:'Immortal',
    107:'Probe',
    108:'Interceptor',
    109:'Hatchery',
    110:'CreepTumor',
    111:'Extractor',
    112:'SpawningPool',
    113:'EvolutionChamber',
    114:'HydraliskDen',
    115:'Spire',
    116:'UltraliskCavern',
    117:'InfestationPit',
    118:'NydusNetwork',
    119:'BanelingNest',
    120:'RoachWarren',
    121:'SpineCrawler',
    122:'SporeCrawler',
    123:'Lair',
    124:'Hive',
    125:'GreaterSpire',
    126:'Egg',
    127:'Drone',
    128:'Zergling',
    129:'Overlord',
    130:'Hydralisk',
    131:'Mutalisk',
    132:'Ultralisk',
    133:'Roach',
    134:'Infestor',
    135:'Corruptor',
    136:'BroodLordCocoon',
    137:'BroodLord',
    138:'BanelingBurrowed',
    139:'DroneBurrowed',
    140:'HydraliskBurrowed',
    141:'RoachBurrowed',
    142:'ZerglingBurrowed',
    143:'InfestorTerranBurrowed',
    144:'RedstoneLavaCritterBurrowed',
    145:'RedstoneLavaCritterInjuredBurrowed',
    146:'RedstoneLavaCritter',
    147:'RedstoneLavaCritterInjured',
    148:'QueenBurrowed',
    149:'Queen',
    150:'InfestorBurrowed',
    151:'OverlordCocoon',
    152:'Overseer',
    153:'PlanetaryFortress',
    154:'UltraliskBurrowed',
    155:'OrbitalCommand',
    156:'WarpGate',
    157:'OrbitalCommandFlying',
    158:'ForceField',
    159:'WarpPrismPhasing',
    160:'CreepTumorBurrowed',
    161:'CreepTumorQueen',
    162:'SpineCrawlerUprooted',
    163:'SporeCrawlerUprooted',
    164:'Archon',
    165:'NydusCanal',
    166:'BroodlingEscort',
    167:'GhostAlternate',
    168:'GhostNova',
    169:'RichMineralField',
    170:'RichMineralField750',
    171:'Ursadon',
    173:'LurkerMPBurrowed',
    174:'LurkerMP',
    175:'LurkerDenMP',
    176:'LurkerMPEgg',
    177:'NydusCanalAttacker',
    178:'OverlordTransport',
    179:'Ravager',
    180:'RavagerBurrowed',
    181:'RavagerCocoon',
    182:'TransportOverlordCocoon',
    183:'XelNagaTower',
    185:'Oracle',
    186:'Tempest',
    188:'InfestedTerransEgg',
    189:'Larva',
    190:'OverseerSiegeMode',
    192:'ReaperPlaceholder',
    193:'MarineACGluescreenDummy',
    194:'FirebatACGluescreenDummy',
    195:'MedicACGluescreenDummy',
    196:'MarauderACGluescreenDummy',
    197:'VultureACGluescreenDummy',
    198:'SiegeTankACGluescreenDummy',
    199:'VikingACGluescreenDummy',
    200:'BansheeACGluescreenDummy',
    201:'BattlecruiserACGluescreenDummy',
    202:'OrbitalCommandACGluescreenDummy',
    203:'BunkerACGluescreenDummy',
    204:'BunkerUpgradedACGluescreenDummy',
    205:'MissileTurretACGluescreenDummy',
    206:'HellbatACGluescreenDummy',
    207:'GoliathACGluescreenDummy',
    208:'CycloneACGluescreenDummy',
    209:'WraithACGluescreenDummy',
    210:'ScienceVesselACGluescreenDummy',
    211:'HerculesACGluescreenDummy',
    212:'ThorACGluescreenDummy',
    213:'PerditionTurretACGluescreenDummy',
    214:'FlamingBettyACGluescreenDummy',
    215:'DevastationTurretACGluescreenDummy',
    216:'BlasterBillyACGluescreenDummy',
    217:'SpinningDizzyACGluescreenDummy',
    218:'ZerglingKerriganACGluescreenDummy',
    219:'RaptorACGluescreenDummy',
    220:'QueenCoopACGluescreenDummy',
    221:'HydraliskACGluescreenDummy',
    222:'HydraliskLurkerACGluescreenDummy',
    223:'MutaliskBroodlordACGluescreenDummy',
    224:'BroodLordACGluescreenDummy',
    225:'UltraliskACGluescreenDummy',
    226:'TorrasqueACGluescreenDummy',
    227:'OverseerACGluescreenDummy',
    228:'LurkerACGluescreenDummy',
    229:'SpineCrawlerACGluescreenDummy',
    230:'SporeCrawlerACGluescreenDummy',
    231:'NydusNetworkACGluescreenDummy',
    232:'OmegaNetworkACGluescreenDummy',
    233:'ZerglingZagaraACGluescreenDummy',
    234:'SwarmlingACGluescreenDummy',
    235:'QueenZagaraACGluescreenDummy',
    236:'BanelingACGluescreenDummy',
    237:'SplitterlingACGluescreenDummy',
    238:'AberrationACGluescreenDummy',
    239:'ScourgeACGluescreenDummy',
    240:'CorruptorACGluescreenDummy',
    241:'OverseerZagaraACGluescreenDummy',
    242:'BileLauncherACGluescreenDummy',
    243:'SwarmQueenACGluescreenDummy',
    244:'RoachACGluescreenDummy',
    245:'RoachVileACGluescreenDummy',
    246:'RavagerACGluescreenDummy',
    247:'SwarmHostACGluescreenDummy',
    248:'MutaliskACGluescreenDummy',
    249:'GuardianACGluescreenDummy',
    250:'DevourerACGluescreenDummy',
    251:'ViperACGluescreenDummy',
    252:'BrutaliskACGluescreenDummy',
    253:'LeviathanACGluescreenDummy',
    254:'ZealotACGluescreenDummy',
    255:'ZealotAiurACGluescreenDummy',
    256:'DragoonACGluescreenDummy',
    257:'HighTemplarACGluescreenDummy',
    258:'ArchonACGluescreenDummy',
    259:'ImmortalACGluescreenDummy',
    260:'ObserverACGluescreenDummy',
    261:'PhoenixAiurACGluescreenDummy',
    262:'ReaverACGluescreenDummy',
    263:'TempestACGluescreenDummy',
    264:'PhotonCannonACGluescreenDummy',
    265:'ZealotVorazunACGluescreenDummy',
    266:'ZealotShakurasACGluescreenDummy',
    267:'StalkerShakurasACGluescreenDummy',
    268:'DarkTemplarShakurasACGluescreenDummy',
    269:'CorsairACGluescreenDummy',
    270:'VoidRayACGluescreenDummy',
    271:'VoidRayShakurasACGluescreenDummy',
    272:'OracleACGluescreenDummy',
    273:'DarkArchonACGluescreenDummy',
    274:'DarkPylonACGluescreenDummy',
    275:'ZealotPurifierACGluescreenDummy',
    276:'SentryPurifierACGluescreenDummy',
    277:'ImmortalKaraxACGluescreenDummy',
    278:'ColossusACGluescreenDummy',
    279:'ColossusPurifierACGluescreenDummy',
    280:'PhoenixPurifierACGluescreenDummy',
    281:'CarrierACGluescreenDummy',
    282:'CarrierAiurACGluescreenDummy',
    283:'KhaydarinMonolithACGluescreenDummy',
    284:'ShieldBatteryACGluescreenDummy',
    285:'EliteMarineACGluescreenDummy',
    286:'MarauderCommandoACGluescreenDummy',
    287:'SpecOpsGhostACGluescreenDummy',
    288:'HellbatRangerACGluescreenDummy',
    289:'StrikeGoliathACGluescreenDummy',
    290:'HeavySiegeTankACGluescreenDummy',
    291:'RaidLiberatorACGluescreenDummy',
    292:'RavenTypeIIACGluescreenDummy',
    293:'CovertBansheeACGluescreenDummy',
    294:'RailgunTurretACGluescreenDummy',
    295:'BlackOpsMissileTurretACGluescreenDummy',
    296:'SupplicantACGluescreenDummy',
    297:'StalkerTaldarimACGluescreenDummy',
    298:'SentryTaldarimACGluescreenDummy',
    299:'HighTemplarTaldarimACGluescreenDummy',
    300:'ImmortalTaldarimACGluescreenDummy',
    301:'ColossusTaldarimACGluescreenDummy',
    302:'WarpPrismTaldarimACGluescreenDummy',
    303:'PhotonCannonTaldarimACGluescreenDummy',
    304:'StukovInfestedCivilianACGluescreenDummy',
    305:'StukovInfestedMarineACGluescreenDummy',
    306:'StukovInfestedSiegeTankACGluescreenDummy',
    307:'StukovInfestedDiamondbackACGluescreenDummy',
    308:'StukovInfestedBansheeACGluescreenDummy',
    309:'SILiberatorACGluescreenDummy',
    310:'StukovInfestedBunkerACGluescreenDummy',
    311:'StukovInfestedMissileTurretACGluescreenDummy',
    312:'StukovBroodQueenACGluescreenDummy',
    313:'ZealotFenixACGluescreenDummy',
    314:'SentryFenixACGluescreenDummy',
    315:'AdeptFenixACGluescreenDummy',
    316:'ImmortalFenixACGluescreenDummy',
    317:'ColossusFenixACGluescreenDummy',
    318:'DisruptorACGluescreenDummy',
    319:'ObserverFenixACGluescreenDummy',
    320:'ScoutACGluescreenDummy',
    321:'CarrierFenixACGluescreenDummy',
    322:'PhotonCannonFenixACGluescreenDummy',
    323:'PrimalZerglingACGluescreenDummy',
    324:'RavasaurACGluescreenDummy',
    325:'PrimalRoachACGluescreenDummy',
    326:'FireRoachACGluescreenDummy',
    327:'PrimalGuardianACGluescreenDummy',
    328:'PrimalHydraliskACGluescreenDummy',
    329:'PrimalMutaliskACGluescreenDummy',
    330:'PrimalImpalerACGluescreenDummy',
    331:'PrimalSwarmHostACGluescreenDummy',
    332:'CreeperHostACGluescreenDummy',
    333:'PrimalUltraliskACGluescreenDummy',
    334:'TyrannozorACGluescreenDummy',
    335:'PrimalWurmACGluescreenDummy',
    336:'HHReaperACGluescreenDummy',
    337:'HHWidowMineACGluescreenDummy',
    338:'HHHellionTankACGluescreenDummy',
    339:'HHWraithACGluescreenDummy',
    340:'HHVikingACGluescreenDummy',
    341:'HHBattlecruiserACGluescreenDummy',
    342:'HHRavenACGluescreenDummy',
    343:'HHBomberPlatformACGluescreenDummy',
    344:'HHMercStarportACGluescreenDummy',
    345:'HHMissileTurretACGluescreenDummy',
    346:'TychusReaperACGluescreenDummy',
    347:'TychusFirebatACGluescreenDummy',
    348:'TychusSpectreACGluescreenDummy',
    349:'TychusMedicACGluescreenDummy',
    350:'TychusMarauderACGluescreenDummy',
    351:'TychusWarhoundACGluescreenDummy',
    352:'TychusHERCACGluescreenDummy',
    353:'TychusGhostACGluescreenDummy',
    354:'TychusSCVAutoTurretACGluescreenDummy',
    355:'ZeratulStalkerACGluescreenDummy',
    356:'ZeratulSentryACGluescreenDummy',
    357:'ZeratulDarkTemplarACGluescreenDummy',
    358:'ZeratulImmortalACGluescreenDummy',
    359:'ZeratulObserverACGluescreenDummy',
    360:'ZeratulDisruptorACGluescreenDummy',
    361:'ZeratulWarpPrismACGluescreenDummy',
    362:'ZeratulPhotonCannonACGluescreenDummy',
    363:'MechaZerglingACGluescreenDummy',
    364:'MechaBanelingACGluescreenDummy',
    365:'MechaHydraliskACGluescreenDummy',
    366:'MechaInfestorACGluescreenDummy',
    367:'MechaCorruptorACGluescreenDummy',
    368:'MechaUltraliskACGluescreenDummy',
    369:'MechaOverseerACGluescreenDummy',
    370:'MechaLurkerACGluescreenDummy',
    371:'MechaBattlecarrierLordACGluescreenDummy',
    372:'MechaSpineCrawlerACGluescreenDummy',
    373:'MechaSporeCrawlerACGluescreenDummy',
    374:'TrooperMengskACGluescreenDummy',
    375:'MedivacMengskACGluescreenDummy',
    376:'BlimpMengskACGluescreenDummy',
    377:'MarauderMengskACGluescreenDummy',
    378:'GhostMengskACGluescreenDummy',
    379:'SiegeTankMengskACGluescreenDummy',
    380:'ThorMengskACGluescreenDummy',
    381:'VikingMengskACGluescreenDummy',
    382:'BattlecruiserMengskACGluescreenDummy',
    383:'BunkerDepotMengskACGluescreenDummy',
    384:'MissileTurretMengskACGluescreenDummy',
    385:'ArtilleryMengskACGluescreenDummy',
    387:'RenegadeLongboltMissileWeapon',
    388:'LoadOutSpray@1',
    389:'LoadOutSpray@2',
    390:'LoadOutSpray@3',
    391:'LoadOutSpray@4',
    392:'LoadOutSpray@5',
    393:'LoadOutSpray@6',
    394:'LoadOutSpray@7',
    395:'LoadOutSpray@8',
    396:'LoadOutSpray@9',
    397:'LoadOutSpray@10',
    398:'LoadOutSpray@11',
    399:'LoadOutSpray@12',
    400:'LoadOutSpray@13',
    401:'LoadOutSpray@14',
    402:'NeedleSpinesWeapon',
    403:'CorruptionWeapon',
    404:'InfestedTerransWeapon',
    405:'NeuralParasiteWeapon',
    406:'PointDefenseDroneReleaseWeapon',
    407:'HunterSeekerWeapon',
    408:'MULE',
    410:'ThorAAWeapon',
    411:'PunisherGrenadesLMWeapon',
    412:'VikingFighterWeapon',
    413:'ATALaserBatteryLMWeapon',
    414:'ATSLaserBatteryLMWeapon',
    415:'LongboltMissileWeapon',
    416:'D8ChargeWeapon',
    417:'YamatoWeapon',
    418:'IonCannonsWeapon',
    419:'AcidSalivaWeapon',
    420:'SpineCrawlerWeapon',
    421:'SporeCrawlerWeapon',
    422:'GlaiveWurmWeapon',
    423:'GlaiveWurmM2Weapon',
    424:'GlaiveWurmM3Weapon',
    425:'StalkerWeapon',
    426:'EMP2Weapon',
    427:'BacklashRocketsLMWeapon',
    428:'PhotonCannonWeapon',
    429:'ParasiteSporeWeapon',
    431:'Broodling',
    432:'BroodLordBWeapon',
    435:'AutoTurretReleaseWeapon',
    436:'LarvaReleaseMissile',
    437:'AcidSpinesWeapon',
    438:'FrenzyWeapon',
    439:'ContaminateWeapon',
    451:'BeaconArmy',
    452:'BeaconDefend',
    453:'BeaconAttack',
    454:'BeaconHarass',
    455:'BeaconIdle',
    456:'BeaconAuto',
    457:'BeaconDetect',
    458:'BeaconScout',
    459:'BeaconClaim',
    460:'BeaconExpand',
    461:'BeaconRally',
    462:'BeaconCustom1',
    463:'BeaconCustom2',
    464:'BeaconCustom3',
    465:'BeaconCustom4',
    470:'LiberatorAG',
    472:'PreviewBunkerUpgraded',
    473:'HellionTank',
    474:'Cyclone',
    475:'WidowMine',
    476:'Liberator',
    478:'Adept',
    479:'Disruptor',
    480:'SwarmHostMP',
    481:'Viper',
    482:'ShieldBattery',
    483:'HighTemplarSkinPreview',
    484:'MothershipCore',
    485:'Viking',
    498:'InhibitorZoneSmall',
    499:'InhibitorZoneMedium',
    500:'InhibitorZoneLarge',
    501:'AccelerationZoneSmall',
    502:'AccelerationZoneMedium',
    503:'AccelerationZoneLarge',
    504:'AccelerationZoneFlyingSmall',
    505:'AccelerationZoneFlyingMedium',
    506:'AccelerationZoneFlyingLarge',
    507:'InhibitorZoneFlyingSmall',
    508:'InhibitorZoneFlyingMedium',
    509:'InhibitorZoneFlyingLarge',
    510:'AssimilatorRich',
    511:'RichVespeneGeyser',
    512:'ExtractorRich',
    513:'RavagerCorrosiveBileMissile',
    514:'RavagerWeaponMissile',
    515:'RenegadeMissileTurret',
    516:'Rocks2x2NonConjoined',
    517:'FungalGrowthMissile',
    518:'NeuralParasiteTentacleMissile',
    519:'Beacon_Protoss',
    520:'Beacon_ProtossSmall',
    521:'Beacon_Terran',
    522:'Beacon_TerranSmall',
    523:'Beacon_Zerg',
    524:'Beacon_ZergSmall',
    525:'Lyote',
    526:'CarrionBird',
    527:'KarakMale',
    528:'KarakFemale',
    529:'UrsadakFemaleExotic',
    530:'UrsadakMale',
    531:'UrsadakFemale',
    532:'UrsadakCalf',
    533:'UrsadakMaleExotic',
    534:'UtilityBot',
    535:'CommentatorBot1',
    536:'CommentatorBot2',
    537:'CommentatorBot3',
    538:'CommentatorBot4',
    539:'Scantipede',
    540:'Dog',
    541:'Sheep',
    542:'Cow',
    543:'InfestedTerransEggPlacement',
    544:'InfestorTerransWeapon',
    545:'MineralField',
    546:'MineralField450',
    547:'MineralField750',
    548:'MineralFieldOpaque',
    549:'MineralFieldOpaque900',
    550:'VespeneGeyser',
    551:'SpacePlatformGeyser',
    552:'DestructibleSearchlight',
    553:'DestructibleBullhornLights',
    554:'DestructibleStreetlight',
    555:'DestructibleSpacePlatformSign',
    556:'DestructibleStoreFrontCityProps',
    557:'DestructibleBillboardTall',
    558:'DestructibleBillboardScrollingText',
    559:'DestructibleSpacePlatformBarrier',
    560:'DestructibleSignsDirectional',
    561:'DestructibleSignsConstruction',
    562:'DestructibleSignsFunny',
    563:'DestructibleSignsIcons',
    564:'DestructibleSignsWarning',
    565:'DestructibleGarage',
    566:'DestructibleGarageLarge',
    567:'DestructibleTrafficSignal',
    568:'TrafficSignal',
    569:'BraxisAlphaDestructible1x1',
    570:'BraxisAlphaDestructible2x2',
    571:'DestructibleDebris4x4',
    572:'DestructibleDebris6x6',
    573:'DestructibleRock2x4Vertical',
    574:'DestructibleRock2x4Horizontal',
    575:'DestructibleRock2x6Vertical',
    576:'DestructibleRock2x6Horizontal',
    577:'DestructibleRock4x4',
    578:'DestructibleRock6x6',
    579:'DestructibleRampDiagonalHugeULBR',
    580:'DestructibleRampDiagonalHugeBLUR',
    581:'DestructibleRampVerticalHuge',
    582:'DestructibleRampHorizontalHuge',
    583:'DestructibleDebrisRampDiagonalHugeULBR',
    584:'DestructibleDebrisRampDiagonalHugeBLUR',
    585:'WarpPrismSkinPreview',
    586:'SiegeTankSkinPreview',
    587:'ThorAP',
    588:'ThorAALance',
    589:'LiberatorSkinPreview',
    590:'OverlordGenerateCreepKeybind',
    591:'MengskStatueAlone',
    592:'MengskStatue',
    593:'WolfStatue',
    594:'GlobeStatue',
    595:'Weapon',
    596:'GlaiveWurmBounceWeapon',
    597:'BroodLordWeapon',
    598:'BroodLordAWeapon',
    599:'CreepBlocker1x1',
    600:'PermanentCreepBlocker1x1',
    601:'PathingBlocker1x1',
    602:'PathingBlocker2x2',
    603:'AutoTestAttackTargetGround',
    604:'AutoTestAttackTargetAir',
    605:'AutoTestAttacker',
    606:'HelperEmitterSelectionArrow',
    607:'MultiKillObject',
    608:'ShapeGolfball',
    609:'ShapeCone',
    610:'ShapeCube',
    611:'ShapeCylinder',
    612:'ShapeDodecahedron',
    613:'ShapeIcosahedron',
    614:'ShapeOctahedron',
    615:'ShapePyramid',
    616:'ShapeRoundedCube',
    617:'ShapeSphere',
    618:'ShapeTetrahedron',
    619:'ShapeThickTorus',
    620:'ShapeThinTorus',
    621:'ShapeTorus',
    622:'Shape4PointStar',
    623:'Shape5PointStar',
    624:'Shape6PointStar',
    625:'Shape8PointStar',
    626:'ShapeArrowPointer',
    627:'ShapeBowl',
    628:'ShapeBox',
    629:'ShapeCapsule',
    630:'ShapeCrescentMoon',
    631:'ShapeDecahedron',
    632:'ShapeDiamond',
    633:'ShapeFootball',
    634:'ShapeGemstone',
    635:'ShapeHeart',
    636:'ShapeJack',
    637:'ShapePlusSign',
    638:'ShapeShamrock',
    639:'ShapeSpade',
    640:'ShapeTube',
    641:'ShapeEgg',
    642:'ShapeYenSign',
    643:'ShapeX',
    644:'ShapeWatermelon',
    645:'ShapeWonSign',
    646:'ShapeTennisball',
    647:'ShapeStrawberry',
    648:'ShapeSmileyFace',
    649:'ShapeSoccerball',
    650:'ShapeRainbow',
    651:'ShapeSadFace',
    652:'ShapePoundSign',
    653:'ShapePear',
    654:'ShapePineapple',
    655:'ShapeOrange',
    656:'ShapePeanut',
    657:'ShapeO',
    658:'ShapeLemon',
    659:'ShapeMoneyBag',
    660:'ShapeHorseshoe',
    661:'ShapeHockeyStick',
    662:'ShapeHockeyPuck',
    663:'ShapeHand',
    664:'ShapeGolfClub',
    665:'ShapeGrape',
    666:'ShapeEuroSign',
    667:'ShapeDollarSign',
    668:'ShapeBasketball',
    669:'ShapeCarrot',
    670:'ShapeCherry',
    671:'ShapeBaseball',
    672:'ShapeBaseballBat',
    673:'ShapeBanana',
    674:'ShapeApple',
    675:'ShapeCashLarge',
    676:'ShapeCashMedium',
    677:'ShapeCashSmall',
    678:'ShapeFootballColored',
    679:'ShapeLemonSmall',
    680:'ShapeOrangeSmall',
    681:'ShapeTreasureChestOpen',
    682:'ShapeTreasureChestClosed',
    683:'ShapeWatermelonSmall',
    684:'UnbuildableRocksDestructible',
    685:'UnbuildableBricksDestructible',
    686:'UnbuildablePlatesDestructible',
    687:'Debris2x2NonConjoined',
    688:'EnemyPathingBlocker1x1',
    689:'EnemyPathingBlocker2x2',
    690:'EnemyPathingBlocker4x4',
    691:'EnemyPathingBlocker8x8',
    692:'EnemyPathingBlocker16x16',
    693:'ScopeTest',
    694:'SentryACGluescreenDummy',
    695:'StukovInfestedTrooperACGluescreenDummy',
    711:'CollapsibleTerranTowerDebris',
    712:'DebrisRampLeft',
    713:'DebrisRampRight',
    717:'LocustMP',
    718:'CollapsibleRockTowerDebris',
    719:'NydusCanalCreeper',
    720:'SwarmHostBurrowedMP',
    721:'WarHound',
    722:'WidowMineBurrowed',
    723:'ExtendingBridgeNEWide8Out',
    724:'ExtendingBridgeNEWide8',
    725:'ExtendingBridgeNWWide8Out',
    726:'ExtendingBridgeNWWide8',
    727:'ExtendingBridgeNEWide10Out',
    728:'ExtendingBridgeNEWide10',
    729:'ExtendingBridgeNWWide10Out',
    730:'ExtendingBridgeNWWide10',
    731:'ExtendingBridgeNEWide12Out',
    732:'ExtendingBridgeNEWide12',
    733:'ExtendingBridgeNWWide12Out',
    734:'ExtendingBridgeNWWide12',
    736:'CollapsibleRockTowerDebrisRampRight',
    737:'CollapsibleRockTowerDebrisRampLeft',
    738:'XelNaga_Caverns_DoorE',
    739:'XelNaga_Caverns_DoorEOpened',
    740:'XelNaga_Caverns_DoorN',
    741:'XelNaga_Caverns_DoorNE',
    742:'XelNaga_Caverns_DoorNEOpened',
    743:'XelNaga_Caverns_DoorNOpened',
    744:'XelNaga_Caverns_DoorNW',
    745:'XelNaga_Caverns_DoorNWOpened',
    746:'XelNaga_Caverns_DoorS',
    747:'XelNaga_Caverns_DoorSE',
    748:'XelNaga_Caverns_DoorSEOpened',
    749:'XelNaga_Caverns_DoorSOpened',
    750:'XelNaga_Caverns_DoorSW',
    751:'XelNaga_Caverns_DoorSWOpened',
    752:'XelNaga_Caverns_DoorW',
    753:'XelNaga_Caverns_DoorWOpened',
    754:'XelNaga_Caverns_Floating_BridgeNE8Out',
    755:'XelNaga_Caverns_Floating_BridgeNE8',
    756:'XelNaga_Caverns_Floating_BridgeNW8Out',
    757:'XelNaga_Caverns_Floating_BridgeNW8',
    758:'XelNaga_Caverns_Floating_BridgeNE10Out',
    759:'XelNaga_Caverns_Floating_BridgeNE10',
    760:'XelNaga_Caverns_Floating_BridgeNW10Out',
    761:'XelNaga_Caverns_Floating_BridgeNW10',
    762:'XelNaga_Caverns_Floating_BridgeNE12Out',
    763:'XelNaga_Caverns_Floating_BridgeNE12',
    764:'XelNaga_Caverns_Floating_BridgeNW12Out',
    765:'XelNaga_Caverns_Floating_BridgeNW12',
    766:'XelNaga_Caverns_Floating_BridgeH8Out',
    767:'XelNaga_Caverns_Floating_BridgeH8',
    768:'XelNaga_Caverns_Floating_BridgeV8Out',
    769:'XelNaga_Caverns_Floating_BridgeV8',
    770:'XelNaga_Caverns_Floating_BridgeH10Out',
    771:'XelNaga_Caverns_Floating_BridgeH10',
    772:'XelNaga_Caverns_Floating_BridgeV10Out',
    773:'XelNaga_Caverns_Floating_BridgeV10',
    774:'XelNaga_Caverns_Floating_BridgeH12Out',
    775:'XelNaga_Caverns_Floating_BridgeH12',
    776:'XelNaga_Caverns_Floating_BridgeV12Out',
    777:'XelNaga_Caverns_Floating_BridgeV12',
    780:'CollapsibleTerranTowerPushUnitRampLeft',
    781:'CollapsibleTerranTowerPushUnitRampRight',
    784:'CollapsibleRockTowerPushUnit',
    785:'CollapsibleTerranTowerPushUnit',
    786:'CollapsibleRockTowerPushUnitRampRight',
    787:'CollapsibleRockTowerPushUnitRampLeft',
    788:'DigesterCreepSprayTargetUnit',
    789:'DigesterCreepSprayUnit',
    790:'NydusCanalAttackerWeapon',
    791:'ViperConsumeStructureWeapon',
    794:'ResourceBlocker',
    795:'TempestWeapon',
    796:'YoinkMissile',
    800:'YoinkVikingAirMissile',
    802:'YoinkVikingGroundMissile',
    804:'YoinkSiegeTankMissile',
    806:'WarHoundWeapon',
    808:'EyeStalkWeapon',
    811:'WidowMineWeapon',
    812:'WidowMineAirWeapon',
    813:'MothershipCoreWeaponWeapon',
    814:'TornadoMissileWeapon',
    815:'TornadoMissileDummyWeapon',
    816:'TalonsMissileWeapon',
    817:'CreepTumorMissile',
    818:'LocustMPEggAMissileWeapon',
    819:'LocustMPEggBMissileWeapon',
    820:'LocustMPWeapon',
    822:'RepulsorCannonWeapon',
    826:'CollapsibleRockTowerDiagonal',
    827:'CollapsibleTerranTowerDiagonal',
    828:'CollapsibleTerranTowerRampLeft',
    829:'CollapsibleTerranTowerRampRight',
    830:'Ice2x2NonConjoined',
    831:'IceProtossCrates',
    832:'ProtossCrates',
    833:'TowerMine',
    834:'PickupPalletGas',
    835:'PickupPalletMinerals',
    836:'PickupScrapSalvage1x1',
    837:'PickupScrapSalvage2x2',
    838:'PickupScrapSalvage3x3',
    839:'RoughTerrain',
    840:'UnbuildableBricksSmallUnit',
    841:'UnbuildablePlatesSmallUnit',
    842:'UnbuildablePlatesUnit',
    843:'UnbuildableRocksSmallUnit',
    844:'XelNagaHealingShrine',
    845:'InvisibleTargetDummy',
    846:'ProtossVespeneGeyser',
    847:'CollapsibleRockTower',
    848:'CollapsibleTerranTower',
    849:'ThornLizard',
    850:'CleaningBot',
    851:'DestructibleRock6x6Weak',
    852:'ProtossSnakeSegmentDemo',
    853:'PhysicsCapsule',
    854:'PhysicsCube',
    855:'PhysicsCylinder',
    856:'PhysicsKnot',
    857:'PhysicsL',
    858:'PhysicsPrimitives',
    859:'PhysicsSphere',
    860:'PhysicsStar',
    861:'CreepBlocker4x4',
    862:'DestructibleCityDebris2x4Vertical',
    863:'DestructibleCityDebris2x4Horizontal',
    864:'DestructibleCityDebris2x6Vertical',
    865:'DestructibleCityDebris2x6Horizontal',
    866:'DestructibleCityDebris4x4',
    867:'DestructibleCityDebris6x6',
    868:'DestructibleCityDebrisHugeDiagonalBLUR',
    869:'DestructibleCityDebrisHugeDiagonalULBR',
    870:'TestZerg',
    871:'PathingBlockerRadius1',
    872:'DestructibleRockEx12x4Vertical',
    873:'DestructibleRockEx12x4Horizontal',
    874:'DestructibleRockEx12x6Vertical',
    875:'DestructibleRockEx12x6Horizontal',
    876:'DestructibleRockEx14x4',
    877:'DestructibleRockEx16x6',
    878:'DestructibleRockEx1DiagonalHugeULBR',
    879:'DestructibleRockEx1DiagonalHugeBLUR',
    880:'DestructibleRockEx1VerticalHuge',
    881:'DestructibleRockEx1HorizontalHuge',
    882:'DestructibleIce2x4Vertical',
    883:'DestructibleIce2x4Horizontal',
    884:'DestructibleIce2x6Vertical',
    885:'DestructibleIce2x6Horizontal',
    886:'DestructibleIce4x4',
    887:'DestructibleIce6x6',
    888:'DestructibleIceDiagonalHugeULBR',
    889:'DestructibleIceDiagonalHugeBLUR',
    890:'DestructibleIceVerticalHuge',
    891:'DestructibleIceHorizontalHuge',
    892:'DesertPlanetSearchlight',
    893:'DesertPlanetStreetlight',
    894:'UnbuildableBricksUnit',
    895:'UnbuildableRocksUnit',
    896:'ZerusDestructibleArch',
    897:'Artosilope',
    898:'Anteplott',
    899:'LabBot',
    900:'Crabeetle',
    901:'CollapsibleRockTowerRampRight',
    902:'CollapsibleRockTowerRampLeft',
    903:'LabMineralField',
    904:'LabMineralField750',
    919:'CollapsibleRockTowerDebrisRampLeftGreen',
    920:'CollapsibleRockTowerDebrisRampRightGreen',
    921:'SnowRefinery_Terran_ExtendingBridgeNEShort8Out',
    922:'SnowRefinery_Terran_ExtendingBridgeNEShort8',
    923:'SnowRefinery_Terran_ExtendingBridgeNWShort8Out',
    924:'SnowRefinery_Terran_ExtendingBridgeNWShort8',
    929:'Tarsonis_DoorN',
    930:'Tarsonis_DoorNLowered',
    931:'Tarsonis_DoorNE',
    932:'Tarsonis_DoorNELowered',
    933:'Tarsonis_DoorE',
    934:'Tarsonis_DoorELowered',
    935:'Tarsonis_DoorNW',
    936:'Tarsonis_DoorNWLowered',
    937:'CompoundMansion_DoorN',
    938:'CompoundMansion_DoorNLowered',
    939:'CompoundMansion_DoorNE',
    940:'CompoundMansion_DoorNELowered',
    941:'CompoundMansion_DoorE',
    942:'CompoundMansion_DoorELowered',
    943:'CompoundMansion_DoorNW',
    944:'CompoundMansion_DoorNWLowered',
    946:'LocustMPFlying',
    947:'AiurLightBridgeNE8Out',
    948:'AiurLightBridgeNE8',
    949:'AiurLightBridgeNE10Out',
    950:'AiurLightBridgeNE10',
    951:'AiurLightBridgeNE12Out',
    952:'AiurLightBridgeNE12',
    953:'AiurLightBridgeNW8Out',
    954:'AiurLightBridgeNW8',
    955:'AiurLightBridgeNW10Out',
    956:'AiurLightBridgeNW10',
    957:'AiurLightBridgeNW12Out',
    958:'AiurLightBridgeNW12',
    959:'AiurTempleBridgeNE8Out',
    961:'AiurTempleBridgeNE10Out',
    963:'AiurTempleBridgeNE12Out',
    965:'AiurTempleBridgeNW8Out',
    967:'AiurTempleBridgeNW10Out',
    969:'AiurTempleBridgeNW12Out',
    971:'ShakurasLightBridgeNE8Out',
    972:'ShakurasLightBridgeNE8',
    973:'ShakurasLightBridgeNE10Out',
    974:'ShakurasLightBridgeNE10',
    975:'ShakurasLightBridgeNE12Out',
    976:'ShakurasLightBridgeNE12',
    977:'ShakurasLightBridgeNW8Out',
    978:'ShakurasLightBridgeNW8',
    979:'ShakurasLightBridgeNW10Out',
    980:'ShakurasLightBridgeNW10',
    981:'ShakurasLightBridgeNW12Out',
    982:'ShakurasLightBridgeNW12',
    983:'VoidMPImmortalReviveCorpse',
    984:'GuardianCocoonMP',
    985:'GuardianMP',
    986:'DevourerCocoonMP',
    987:'DevourerMP',
    988:'DefilerMPBurrowed',
    989:'DefilerMP',
    990:'OracleStasisTrap',
    991:'DisruptorPhased',
    992:'AiurLightBridgeAbandonedNE8Out',
    993:'AiurLightBridgeAbandonedNE8',
    994:'AiurLightBridgeAbandonedNE10Out',
    995:'AiurLightBridgeAbandonedNE10',
    996:'AiurLightBridgeAbandonedNE12Out',
    997:'AiurLightBridgeAbandonedNE12',
    998:'AiurLightBridgeAbandonedNW8Out',
    999:'AiurLightBridgeAbandonedNW8',
    1000:'AiurLightBridgeAbandonedNW10Out',
    1001:'AiurLightBridgeAbandonedNW10',
    1002:'AiurLightBridgeAbandonedNW12Out',
    1003:'AiurLightBridgeAbandonedNW12',
    1004:'CollapsiblePurifierTowerDebris',
    1005:'PortCity_Bridge_UnitNE8Out',
    1006:'PortCity_Bridge_UnitNE8',
    1007:'PortCity_Bridge_UnitSE8Out',
    1008:'PortCity_Bridge_UnitSE8',
    1009:'PortCity_Bridge_UnitNW8Out',
    1010:'PortCity_Bridge_UnitNW8',
    1011:'PortCity_Bridge_UnitSW8Out',
    1012:'PortCity_Bridge_UnitSW8',
    1013:'PortCity_Bridge_UnitNE10Out',
    1014:'PortCity_Bridge_UnitNE10',
    1015:'PortCity_Bridge_UnitSE10Out',
    1016:'PortCity_Bridge_UnitSE10',
    1017:'PortCity_Bridge_UnitNW10Out',
    1018:'PortCity_Bridge_UnitNW10',
    1019:'PortCity_Bridge_UnitSW10Out',
    1020:'PortCity_Bridge_UnitSW10',
    1021:'PortCity_Bridge_UnitNE12Out',
    1022:'PortCity_Bridge_UnitNE12',
    1023:'PortCity_Bridge_UnitSE12Out',
    1024:'PortCity_Bridge_UnitSE12',
    1025:'PortCity_Bridge_UnitNW12Out',
    1026:'PortCity_Bridge_UnitNW12',
    1027:'PortCity_Bridge_UnitSW12Out',
    1028:'PortCity_Bridge_UnitSW12',
    1029:'PortCity_Bridge_UnitN8Out',
    1030:'PortCity_Bridge_UnitN8',
    1031:'PortCity_Bridge_UnitS8Out',
    1032:'PortCity_Bridge_UnitS8',
    1033:'PortCity_Bridge_UnitE8Out',
    1034:'PortCity_Bridge_UnitE8',
    1035:'PortCity_Bridge_UnitW8Out',
    1036:'PortCity_Bridge_UnitW8',
    1037:'PortCity_Bridge_UnitN10Out',
    1038:'PortCity_Bridge_UnitN10',
    1039:'PortCity_Bridge_UnitS10Out',
    1040:'PortCity_Bridge_UnitS10',
    1041:'PortCity_Bridge_UnitE10Out',
    1042:'PortCity_Bridge_UnitE10',
    1043:'PortCity_Bridge_UnitW10Out',
    1044:'PortCity_Bridge_UnitW10',
    1045:'PortCity_Bridge_UnitN12Out',
    1046:'PortCity_Bridge_UnitN12',
    1047:'PortCity_Bridge_UnitS12Out',
    1048:'PortCity_Bridge_UnitS12',
    1049:'PortCity_Bridge_UnitE12Out',
    1050:'PortCity_Bridge_UnitE12',
    1051:'PortCity_Bridge_UnitW12Out',
    1052:'PortCity_Bridge_UnitW12',
    1053:'PurifierRichMineralField',
    1054:'PurifierRichMineralField750',
    1055:'CollapsibleRockTowerPushUnitRampLeftGreen',
    1056:'CollapsibleRockTowerPushUnitRampRightGreen',
    1071:'CollapsiblePurifierTowerPushUnit',
    1073:'LocustMPPrecursor',
    1074:'ReleaseInterceptorsBeacon',
    1075:'AdeptPhaseShift',
    1076:'HydraliskImpaleMissile',
    1077:'CycloneMissileLargeAir',
    1078:'CycloneMissile',
    1079:'CycloneMissileLarge',
    1080:'OracleWeapon',
    1081:'TempestWeaponGround',
    1082:'ScoutMPAirWeaponLeft',
    1083:'ScoutMPAirWeaponRight',
    1084:'ArbiterMPWeaponMissile',
    1085:'GuardianMPWeapon',
    1086:'DevourerMPWeaponMissile',
    1087:'DefilerMPDarkSwarmWeapon',
    1088:'QueenMPEnsnareMissile',
    1089:'QueenMPSpawnBroodlingsMissile',
    1090:'LightningBombWeapon',
    1091:'HERCPlacement',
    1092:'GrappleWeapon',
    1095:'CausticSprayMissile',
    1096:'ParasiticBombMissile',
    1097:'ParasiticBombDummy',
    1098:'AdeptWeapon',
    1099:'AdeptUpgradeWeapon',
    1100:'LiberatorMissile',
    1101:'LiberatorDamageMissile',
    1102:'LiberatorAGMissile',
    1103:'KD8Charge',
    1104:'KD8ChargeWeapon',
    1106:'SlaynElementalGrabWeapon',
    1107:'SlaynElementalGrabAirUnit',
    1108:'SlaynElementalGrabGroundUnit',
    1109:'SlaynElementalWeapon',
    1114:'CollapsibleRockTowerRampLeftGreen',
    1115:'CollapsibleRockTowerRampRightGreen',
    1116:'DestructibleExpeditionGate6x6',
    1117:'DestructibleZergInfestation3x3',
    1118:'HERC',
    1119:'Moopy',
    1120:'Replicant',
    1121:'SeekerMissile',
    1122:'AiurTempleBridgeDestructibleNE8Out',
    1123:'AiurTempleBridgeDestructibleNE10Out',
    1124:'AiurTempleBridgeDestructibleNE12Out',
    1125:'AiurTempleBridgeDestructibleNW8Out',
    1126:'AiurTempleBridgeDestructibleNW10Out',
    1127:'AiurTempleBridgeDestructibleNW12Out',
    1128:'AiurTempleBridgeDestructibleSW8Out',
    1129:'AiurTempleBridgeDestructibleSW10Out',
    1130:'AiurTempleBridgeDestructibleSW12Out',
    1131:'AiurTempleBridgeDestructibleSE8Out',
    1132:'AiurTempleBridgeDestructibleSE10Out',
    1133:'AiurTempleBridgeDestructibleSE12Out',
    1135:'FlyoverUnit',
    1136:'CorsairMP',
    1137:'ScoutMP',
    1139:'ArbiterMP',
    1140:'ScourgeMP',
    1141:'DefilerMPPlagueWeapon',
    1142:'QueenMP',
    1143:'XelNagaDestructibleRampBlocker6S',
    1144:'XelNagaDestructibleRampBlocker6SE',
    1145:'XelNagaDestructibleRampBlocker6E',
    1146:'XelNagaDestructibleRampBlocker6NE',
    1147:'XelNagaDestructibleRampBlocker6N',
    1148:'XelNagaDestructibleRampBlocker6NW',
    1149:'XelNagaDestructibleRampBlocker6W',
    1150:'XelNagaDestructibleRampBlocker6SW',
    1151:'XelNagaDestructibleRampBlocker8S',
    1152:'XelNagaDestructibleRampBlocker8SE',
    1153:'XelNagaDestructibleRampBlocker8E',
    1154:'XelNagaDestructibleRampBlocker8NE',
    1155:'XelNagaDestructibleRampBlocker8N',
    1156:'XelNagaDestructibleRampBlocker8NW',
    1157:'XelNagaDestructibleRampBlocker8W',
    1158:'XelNagaDestructibleRampBlocker8SW',
    1159:'XelNagaDestructibleBlocker6S',
    1160:'XelNagaDestructibleBlocker6SE',
    1161:'XelNagaDestructibleBlocker6E',
    1162:'XelNagaDestructibleBlocker6NE',
    1163:'XelNagaDestructibleBlocker6N',
    1164:'XelNagaDestructibleBlocker6NW',
    1165:'XelNagaDestructibleBlocker6W',
    1166:'XelNagaDestructibleBlocker6SW',
    1167:'XelNagaDestructibleBlocker8S',
    1168:'XelNagaDestructibleBlocker8SE',
    1169:'XelNagaDestructibleBlocker8E',
    1170:'XelNagaDestructibleBlocker8NE',
    1171:'XelNagaDestructibleBlocker8N',
    1172:'XelNagaDestructibleBlocker8NW',
    1173:'XelNagaDestructibleBlocker8W',
    1174:'XelNagaDestructibleBlocker8SW',
    1175:'ReptileCrate',
    1176:'SlaynSwarmHostSpawnFlyer',
    1177:'SlaynElemental',
    1178:'PurifierVespeneGeyser',
    1179:'ShakurasVespeneGeyser',
    1180:'CollapsiblePurifierTowerDiagonal',
    1181:'CreepOnlyBlocker4x4',
    1182:'BattleStationMineralField',
    1183:'BattleStationMineralField750',
    1184:'PurifierMineralField',
    1185:'PurifierMineralField750',
    1186:'Beacon_Nova',
    1187:'Beacon_NovaSmall',
    1188:'Ursula',
    1189:'Elsecaro_Colonist_Hut',
    1190:'SnowGlazeStarterMP',
    1191:'PylonOvercharged',
    1192:'ObserverSiegeMode',
    1193:'RavenRepairDrone',
    1195:'ParasiticBombRelayDummy',
    1196:'BypassArmorDrone',
    1197:'AdeptPiercingWeapon',
    1198:'HighTemplarWeaponMissile',
    1199:'CycloneMissileLargeAirAlternative',
    1200:'RavenScramblerMissile',
    1201:'RavenRepairDroneReleaseWeapon',
    1202:'RavenShredderMissileWeapon',
    1203:'InfestedAcidSpinesWeapon',
    1204:'InfestorEnsnareAttackMissile',
    1205:'SNARE_PLACEHOLDER',
    1208:'CorrosiveParasiteWeapon'
}