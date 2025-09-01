
import { create } from 'zustand';
import Purchases from 'react-native-purchases';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

type S = {
  pro: boolean;
  initialized: boolean;
  offerings: any | null;
  init: () => Promise<void>;
  refresh: () => Promise<void>;
  purchasePro: (productId?: string) => Promise<boolean>;
};

export const useSession = create<S>((set, get)=> ({
  pro: false,
  initialized: false,
  offerings: null,
  init: async () => {
    const ios = (Constants.expoConfig?.extra as any)?.RC_IOS;
    const android = (Constants.expoConfig?.extra as any)?.RC_ANDROID;
    if (ios || android){
      await Purchases.configure({ apiKey: Platform.select({ ios, android })! });
      const info = await Purchases.getCustomerInfo();
      const has = !!info?.entitlements?.active?.pro;
      let offerings = null;
      try { offerings = await Purchases.getOfferings(); } catch {}
      set({ pro: has, initialized: true, offerings });
    } else {
      set({ initialized: true, offerings: null });
    }
  },
  refresh: async ()=>{
    const info = await Purchases.getCustomerInfo();
    const has = !!info?.entitlements?.active?.pro;
    set({ pro: has });
  },
  purchasePro: async (productId?: string)=>{
    try {
      const offs:any = get().offerings;
      const list = offs?.current?.availablePackages || [];
      const pkg = productId ? list.find((p:any)=>p.identifier===productId) : list[0];
      if (!pkg) return false;
      const res = await Purchases.purchasePackage(pkg);
      await get().refresh();
      return !!res?.customerInfo?.entitlements?.active?.pro;
    } catch {
      return false;
    }
  }
}));
