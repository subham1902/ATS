#ifndef S1_CORE_MQH
#define S1_CORE_MQH
// Same source compiled by MQL5 and the offline C++ parity check.
#ifdef __cplusplus
#define S1_B const std::vector<S1Bar> &h
#define S1_F const std::vector<S1Bar> &f
#else
#define S1_B const S1Bar &h[]
#define S1_F const S1Bar &f[]
#endif
struct S1Bar { long t; double o,h,l,c; int count; };
struct S1Signal { int side; long decision; double atr,low,high,close,level; };
double S1TR(S1_B,int i) {
 double x=h[i].h-h[i].l;
 if(i>0) x=MathMax(x,MathMax(MathAbs(h[i].h-h[i-1].c),MathAbs(h[i].l-h[i-1].c)));
 return x;
}
double S1RMA(S1_B,int end,int period) {
 if(end<period-1) return 0;
 double v=0;for(int i=0;i<period;i++) v+=S1TR(h,i);v/=period;
 for(int i=period;i<=end;i++) v=(v*(period-1)+S1TR(h,i))/period;
 return v;
}
bool S1Calculate(S1_B,S1_F,int hi,int fi,long decision,S1Signal &s) {
 s.side=0;if(hi<64 || fi<12 || hi>=ArraySize(h) || fi>=ArraySize(f)) return false;
 if(h[hi].t+3600!=decision || h[hi].count!=60 || f[fi].count<180) return false;
 int hour=(int)((decision%86400)/3600);if(hour<6 || hour>=20) return false;
 double a=S1RMA(h,hi,14),p=S1RMA(h,hi-1,14),slow=S1RMA(h,hi-1,64);
 if(a<=0 || p<=0 || slow<=0 || p/slow>1.15 || S1TR(h,hi)<1.1*p) return false;
 double upper=h[hi-24].h,lower=h[hi-24].l;
 for(int j=hi-23;j<hi;j++) {upper=MathMax(upper,h[j].h);lower=MathMin(lower,h[j].l);}
 double path=0;for(int j=fi-11;j<=fi;j++) path+=MathAbs(f[j].c-f[j-1].c);
 double mom=f[fi].c-f[fi-12].c;
 if(path<=0 || MathAbs(mom)/path<.25 || h[hi].h<=h[hi].l) return false;
 double loc=(h[hi].c-h[hi].l)/(h[hi].h-h[hi].l);
 if(mom>0 && h[hi].c>=upper && loc>=.70) {s.side=1;s.level=upper;}
 else if(mom<0 && h[hi].c<=lower && loc<=.30) {s.side=-1;s.level=lower;}
 if(s.side==0) return false;
 s.low=h[hi-5].l;s.high=h[hi-5].h;
 for(int j=hi-4;j<=hi;j++) {s.low=MathMin(s.low,h[j].l);s.high=MathMax(s.high,h[j].h);}
 s.decision=decision;s.atr=a;s.close=h[hi].c;return true;
}
#endif
