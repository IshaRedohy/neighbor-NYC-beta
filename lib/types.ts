export interface Profile {
  id: string;
  name: string;
  zip: string;
  occupation: string;
  workplace: string;
  bio: string;
  languages: string[];
  cultures: string[];
  countries: string[];
  expertise: string[];
  interests: string[];
  needs: string[];
  visible: boolean;
  status: string;
  borough: string;
  neighborhood: string;
  lat: number;
  lon: number;
  demo: boolean;
  distance?: number;
  reasons?: string[];
}
export interface Member extends Profile {
  address: string;
  email: string;
  role: "admin" | "member";
}
