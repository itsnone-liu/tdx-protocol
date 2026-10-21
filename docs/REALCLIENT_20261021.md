# Real-client protocol validation — 2026-10-21

## Scope
User-authorized isolated TDX v7.73. Replace Tencent/Sina only after acceptance; neither was queried for these tests. Existing production sources remain unchanged. New implementation: `realclient/cli.py`; Python3 + tdxpy0.2.7 for codecs, direct socket IO and authentic-client-derived bootstrap. No dependency on local17709 for independent quote/exrights acquisition.

## Fresh session / desktop-absent acceptance
Official hosts123.60.164.122 and175.178.112.197 accepted existing284-byte op11 template +8zero suffix. Same123.60.164.122 mixed80stock request: library setup0returned; authentic bootstrap80returned, exact market/code identity set SH30/SZ30/BJ20 after excluding anomalous000004. The anomaly initially returned unexpected600839; CLI rejects substitutions and reports missing/unexpected instead of counting rows as success. Cause remains unknown.

Controlled normal WM_CLOSE+Exit confirmation ended observed TdxW process and closed17709. A subsequent independent fresh connection returned3valid SH/SZ/BJquotes and full-history exrights60012546events/BJ92000215events. Client was restarted and existing login-button path restored17709 without credential reads. See `desktop_absent_v2.json`. This proves no dependency on the desktop process remaining alive for that test, not absence of all possible server-side/shared-IP state. Bootstrap still capture-derived, not a fully understood login generator.

## Actual client price benchmark
Local17709 raw (`none`) and `front` were sampled separately; unfinished20261021 bars excluded to avoid timing differences. Network cat1 fullprecision events:

```
cash = fenhong/10 - peigujia*peigu/10
Ke   = 1 + songzhuangu/10 + peigu/10
# Scan events newest to oldest while walking prices backward:
D = cash + D*Ke
K = K*Ke
front_price = (raw_price-D)/K
```
Ignore events after asof (localgbbq contains future-announced events). Multiple cat1 events on the same day currently fail closed pending a documented normalization rule. Special shrink/rights events not comprehensively covered.

- Targeted16stocks x399completedbars x4OHLC=25,536pricepoints, zero errors >0.01; max~0.00503.
- Frozen-seed20261021 random50stocks with cat1 events in pastyear.49valid baselines,46,880OHLCpoints, zero errors >0.01.601198.SH missing Date in actual-client response; counted as unavailable, not replaced or counted passing. **49/50 stocks passed; not complete50/50 acceptance.**
- Evidence summary JSON committed; raw full client cache datasets and raw network captures stay local.

### Retracted earlier exploratory conclusions
Generic C3 substitution Ke=share_count_after/share_count_before is NOT valid: actual front close mismatches75/399 for301093 and311/399 for688215, whereas cat1 C2 passes. Share-count changes can include effects not equivalent to a price-adjustment event. Do not publish snapshot precision as an established residual cause.
ForwardFactor is a separate client field; raw*ForwardFactor does not reproducefront OHLC (4stock sample max~0.333). Event-step correspondence only explains that field, not price reconstruction. The actual front-price acceptance above uses affine chain.
Official hosts are NOT categorically quote-disabled: their compatibility depends on setup. Broker-host-only claims based on oldlibrary setup are withdrawn.

## Exrights artifacts and authentic batch transport
Localgbbq:4bytecount +193848x29byte records; existing GbbqReader can decrypt. Fourstock cat1 total44events match network fields/dates exactly; file-derived closes also pass4x399. Broader all-category equality verified for those fourstocks only (not market-wide network equality).
Old authentic-client c10 capture has op15batch exrights: request zero6header + lengthu16 twice + op15u16 + countu16 + stocks(marketu8/code6). Response body countu16 then stock(marketu8/code6/eventcountu16/events29B). Event29B=`<B7sIBffff>`:market,code7,dateYYYYMMDD,category,f1..f4. cat1=(dividend,rightsprice,bonusshares,rightsvolume). Historical60stocks1900events matched decryptedlocalgbbq (captured20261016). Current fresh connection4stocks106events,3112bytes, exact boundaries/identities and counts46/29/16/15 equal single-code responses. `xdxr-batch` implements this path.
Whole-filegbbq sync was NOT observed in available captures; binary filename strings alone do not establish its transport. op15content refresh is independently usable without that channel. map watermark exact meaning andcat15semantics remain open.

## Regression and operational limits
8offline tests cover affine cash/split composition, rights payment sign, futureevents, eventdate boundary, duplicatecat1 refusal, symbolvalidation, unexpectedquote refusal. Portability: source contains no Windows API; actualUbuntu execution not performed (localWSL not available). Reconnect/fallback, throughput/fulluniverse, names+floatshares+turnover freshness, realtime timestamp/tradingstate semantics and prolonged snapshot schedule are not accepted yet.

## Run
```
python3 -m pip install -r realclient/requirements.txt
python3 realclient/test_cli.py
python3 realclient/cli.py quotes sh600125 sz000001 bj920002 --bootstrap lab/op11_template.bin
python3 realclient/cli.py xdxr-batch sh600125 bj920002 --bootstrap lab/op11_template.bin
```
The existing template is already tracked in lab; this update does not add private login configs, executable binaries, credential storage or raw capture collections. Server addresses are publicly reachable market-data endpoints, no authenticated account secrets are embedded in newsource.
