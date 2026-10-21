# Ubuntu deployment handoff — NOT YET LIVE-TESTED ON LINUX

## Preconditions and deliverables
Python3.10+; outbound TCP7709 to marketdatahost. Source realclient/cli.py and existing lab/op11_template.bin284bytes. tdxpy==0.2.7 codecs. No Windows DLL/17709/GUI needed in independent CLI commands. Actual Linux package build/network behavior not verified locally. Do NOT install systemwide or assume copied Windowsvenv works.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'tdxpy==0.2.7'
python realclient/cli.py quotes sh600125 sz000001 bj920002 --bootstrap lab/op11_template.bin --out quotes.json
python realclient/cli.py capital-batch sh600125 sz000001 bj920002 --bootstrap lab/op11_template.bin --out capital.json
python realclient/cli.py names bj920002 --bootstrap lab/op11_template.bin --out bj_names.json
python realclient/cli.py qfq-daily sh600125 --count 400 --bootstrap lab/op11_template.bin --out qfq.json
```
The repository update accompanying this handoff includes the commands above; earlier6c02a4c lacks the later features. Run python realclient/test_cli.py before live checks. Requirementscopiedbootstrapmustmatchsha256d8b33ff083caa96a2fd507a0035405e76295f28d1d2ffec2c8e7d0ae1d1bf4d8. This hash bindsobservedtemplate,notguaranteeofperpetualservercompatibility.

## Acceptance checklist (server operator)
1. Archive uname/pythonversion/pipfreeze,selectedhost,templatehash,wallclock andcommands.
2. Runoffline regressiontests (current27). Captureexitcode/stdout/stderr; do notcall200responsealoneregenerationproof.
3. quotesSH/SZ/BJ3stocks:complete=true,requestedidentitiesequalreturned; preservebad/missing/unexpected,neverfillquoteswithpriorstockvalues.
4. capital80mixedbatch:positivefinitefloatshares,reportdata_date;cacheby(market,code,date),do notcallreportdateintradayfreshness.
5. names: market2count389atcurrentWindowsbaseline(expectedcanchange);validatecountandpageidentityandUTF8JSON. codesmustbekeyedwithmarket,notjustcode.
6. qfq comparecompletedbars(actualclientbenchmarkfrozenlocally),excludeactivecandleandapplyasof. Specialcat2/3/4/11/12/15orunknowninthewindowmustfailclosed,notdrop. Same-daymultiplecat1currentlyfailsclosed.
7. ConfirmTDXWindowsclientnotrunningonUbuntu(naturally),no17709dependency. Thirdpartyprovidersnotused.
8. Simulatenetworkfailure:nonzeroexitandnopartialsuccessartifact. Do notreplaceproductionuntilhostretry/cache/schema/monitoringandrestorearetested.

## Time-sensitive tests not substitutable
R4required09:25–09:30actualsynchronizedclientdisplay+rawpackets. R5needsindependentknownhaltgroundtruth. No lunch/no-trade sampleproveshalt. r4_r5_sync_capture.pyrecordsrawandtimestampsbutdoesnotcaptureGUIorproveknownhalt.

## Remaining objective pieces
R2requiresrealclienthistoricalpricesaround2005-2014specialevents(actualcache2021+). R3currentfullmarketnoobservedduplicatecat1soalgorithmunknown. R6opaque272payloadbytes,notcompleteauthgenerator. Existingmainlypublicmarketdatametadatawiremaychange. Respectprovidertermsandratecontrols;fullmarketmeasured8stocksbatch200msgap~373sec,notmaxloadlicense.
